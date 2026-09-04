import os
import json
import pandas as pd
from typing import Dict, Any, List, Optional
from backend.config import GEMINI_API_KEY, ANTHROPIC_API_KEY
from backend.services.scoring import rank_invoices, classify_tier
from backend.services.optimizer import optimize as optimize_offer
from backend.ml.train import predict_acceptance
from backend.services.razorpay import create_payment_link
from backend.db.database import log_event

try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False

MAX_TOOL_ITERATIONS = 8

# Tool declarations for Google Gemini GenAI SDK
if HAS_GEMINI_SDK:
    GEMINI_TOOLS = [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="rank_invoices",
            description="Rank overdue invoices by recoverability score. Use this when the user asks which invoices or customers should be prioritized.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "min_tier": types.Schema(
                        type=types.Type.STRING,
                        description="Optional tier filter: high_priority, standard, low_priority, do_not_contact"
                    )
                }
            )
        ),
        types.FunctionDeclaration(
            name="get_customer_profile",
            description="Retrieve customer invoice details, payment history metrics, LTV, and recoverability score breakdown. Use before analyzing specific invoice options.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "invoice_id": types.Schema(
                        type=types.Type.STRING,
                        description="The invoice ID to retrieve details for (e.g. INV001184)"
                    )
                },
                required=["invoice_id"]
            )
        ),
        types.FunctionDeclaration(
            name="optimize_offer",
            description="Evaluate candidate recovery offers using the machine-learned acceptance model, expected-value calculation, and merchant floor. NEVER manually calculate or invent financial amounts or probabilities.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "invoice_id": types.Schema(
                        type=types.Type.STRING,
                        description="The invoice ID to optimize recovery offers for"
                    ),
                    "merchant_floor": types.Schema(
                        type=types.Type.NUMBER,
                        description="Optional absolute minimum acceptable recovery amount in ₹. If omitted, uses standard default floor calculation."
                    )
                },
                required=["invoice_id"]
            )
        ),
        types.FunctionDeclaration(
            name="create_payment_link",
            description="Create a real Razorpay Test Mode payment link for a recommended recovery offer. Use ONLY when the user explicitly requests to create, generate, send, or execute a payment link. NEVER call this tool when the user is only asking for recommendations or analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "invoice_id": types.Schema(
                        type=types.Type.STRING,
                        description="The invoice ID to create payment link for"
                    ),
                    "offer_amount": types.Schema(
                        type=types.Type.NUMBER,
                        description="The offer amount in ₹ (must be >= merchant floor and match optimizer result)"
                    )
                },
                required=["invoice_id", "offer_amount"]
            )
        )
    ])]
else:
    GEMINI_TOOLS = []

# Tool declarations for Anthropic Tool Calling API
AGENT_TOOLS = [
    {
        "name": "rank_invoices",
        "description": "Rank overdue invoices by recoverability score. Use this when the user asks which invoices or customers should be prioritized.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_tier": {
                    "type": "string",
                    "description": "Optional tier filter: high_priority, standard, low_priority, do_not_contact",
                    "enum": ["high_priority", "standard", "low_priority", "do_not_contact"]
                }
            },
            "required": []
        }
    },
    {
        "name": "get_customer_profile",
        "description": "Retrieve customer invoice details, payment history metrics, LTV, and recoverability score breakdown. Use before analyzing specific invoice options.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {
                    "type": "string",
                    "description": "The invoice ID to retrieve details for (e.g. INV001184)"
                }
            },
            "required": ["invoice_id"]
        }
    },
    {
        "name": "optimize_offer",
        "description": "Evaluate candidate recovery offers using the machine-learned acceptance model, expected-value calculation, and merchant floor. NEVER manually calculate or invent financial amounts or probabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {
                    "type": "string",
                    "description": "The invoice ID to optimize recovery offers for"
                },
                "merchant_floor": {
                    "type": "number",
                    "description": "Optional absolute minimum acceptable recovery amount in ₹. If omitted, uses standard default floor calculation."
                }
            },
            "required": ["invoice_id"]
        }
    },
    {
        "name": "create_payment_link",
        "description": "Create a real Razorpay Test Mode payment link for a recommended recovery offer. Use ONLY when the user explicitly requests to create, generate, send, or execute a payment link. NEVER call this tool when the user is only asking for recommendations or analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {
                    "type": "string",
                    "description": "The invoice ID to create payment link for"
                },
                "offer_amount": {
                    "type": "number",
                    "description": "The offer amount in ₹ (must be >= merchant floor and match optimizer result)"
                }
            },
            "required": ["invoice_id", "offer_amount"]
        }
    }
]

def execute_agent_tool(tool_name: str, tool_input: dict, invoices_df: pd.DataFrame, customers_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Deterministic backend execution of agent tools with strict financial guardrails.
    """
    if tool_name == "rank_invoices":
        min_tier = tool_input.get("min_tier")
        ranked = rank_invoices(invoices_df, customers_df)
        if min_tier:
            ranked = ranked[ranked["tier"] == min_tier]
        top_items = []
        for _, row in ranked.head(10).iterrows():
            top_items.append({
                "invoice_id": str(row["invoice_id"]),
                "customer_id": str(row["customer_id"]),
                "amount": float(row["amount"]),
                "days_overdue": int(row.get("days_overdue", 0)),
                "recovery_score": float(row["recovery_score"]),
                "tier": str(row["tier"])
            })
        return {
            "total_ranked": len(ranked),
            "top_invoices": top_items
        }

    elif tool_name == "get_customer_profile":
        inv_id = str(tool_input.get("invoice_id", ""))
        match_inv = invoices_df[invoices_df["invoice_id"] == inv_id]
        if match_inv.empty:
            return {"error": f"Invoice '{inv_id}' not found"}

        inv_row = match_inv.iloc[0]
        cust_id = str(inv_row["customer_id"])
        match_cust = customers_df[customers_df["customer_id"] == cust_id]

        ranked = rank_invoices(invoices_df, customers_df)
        match_ranked = ranked[ranked["invoice_id"] == inv_id]

        if not match_ranked.empty:
            r_row = match_ranked.iloc[0]
            rec_score = float(r_row["recovery_score"])
            tier = str(r_row["tier"])
            payment_hist = float(r_row["payment_history_score"])
            promise_hist = float(r_row["promise_history_score"])
            ltv_val = float(r_row.get("ltv", 100000.0))
            recency = float(r_row["recency_score"])
            response_hist = float(r_row["response_history_score"])
        else:
            rec_score = 0.5
            tier = "standard"
            payment_hist = 0.5
            promise_hist = 0.5
            ltv_val = 100000.0
            recency = 0.5
            response_hist = 0.5

        return {
            "invoice_id": inv_id,
            "customer_id": cust_id,
            "invoice_amount": float(inv_row["amount"]),
            "days_overdue": int(inv_row.get("days_overdue", 0)),
            "recovery_score": rec_score,
            "tier": tier,
            "customer_metrics": {
                "payment_history_score": payment_hist,
                "promise_history_score": promise_hist,
                "ltv": ltv_val,
                "recency_score": recency,
                "response_history_score": response_hist
            }
        }

    elif tool_name == "optimize_offer":
        inv_id = str(tool_input.get("invoice_id", ""))
        profile = execute_agent_tool("get_customer_profile", {"invoice_id": inv_id}, invoices_df, customers_df)
        if "error" in profile:
            return profile

        inv_amt = profile["invoice_amount"]
        custom_floor = tool_input.get("merchant_floor")
        floor_val = float(custom_floor) if custom_floor is not None else float(round(inv_amt * 0.94))

        cust_feat = {
            "customer_score": profile["recovery_score"],
            "payment_history_score": profile["customer_metrics"]["payment_history_score"],
            "promise_history_score": profile["customer_metrics"]["promise_history_score"],
            "ltv": profile["customer_metrics"]["ltv"],
            "recency_score": profile["customer_metrics"]["recency_score"],
            "response_history_score": profile["customer_metrics"]["response_history_score"],
        }

        res = optimize_offer(
            invoice_amount=inv_amt,
            merchant_floor=floor_val,
            predict_fn=predict_acceptance,
            customer_features=cust_feat
        )

        valid_cands = [c for c in res["all_candidates"] if c["is_valid"]]
        best = res.get("best_offer")

        return {
            "invoice_id": inv_id,
            "invoice_amount": res["original_amount"],
            "merchant_floor": res["merchant_floor"],
            "candidates_evaluated": len(res["all_candidates"]),
            "valid_candidates_count": len(valid_cands),
            "best_offer": best,
            "selection_reason": res.get("selection_reason"),
            "constraints": res.get("constraints")
        }

    elif tool_name == "create_payment_link":
        inv_id = str(tool_input.get("invoice_id", ""))
        requested_amount = float(tool_input.get("offer_amount", 0.0))

        # Financial Safety Guardrail Check
        profile = execute_agent_tool("get_customer_profile", {"invoice_id": inv_id}, invoices_df, customers_df)
        if "error" in profile:
            return profile

        inv_amt = profile["invoice_amount"]
        default_floor = float(round(inv_amt * 0.94))

        if requested_amount < default_floor:
            return {
                "status": "error",
                "error": f"Financial Guardrail Violation: Requested offer amount ₹{requested_amount:,.2f} falls below merchant floor ₹{default_floor:,.2f}."
            }

        try:
            plink_res = create_payment_link(
                invoice_id=inv_id,
                offer_amount=requested_amount,
                customer_email=f"{profile['customer_id'].lower()}@example.com",
                customer_name=profile["customer_id"]
            )

            return {
                "status": "success",
                "invoice_id": inv_id,
                "agreed_amount": requested_amount,
                "payment_link_id": plink_res["id"],
                "payment_link_url": plink_res["short_url"]
            }
        except Exception as err:
            return {
                "status": "warning",
                "invoice_id": inv_id,
                "agreed_amount": requested_amount,
                "message": f"Payment link creation API warning: {str(err)}",
                "payment_link_url": f"https://rzp.io/rzp/demo_{inv_id.lower()}"
            }

    else:
        return {"error": f"Unknown tool '{tool_name}'"}


def run_deterministic_fallback(
    user_message: str,
    invoices_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    fallback_reason: str = "NO_API_KEY",
    error_details: str = ""
) -> Dict[str, Any]:
    """
    Safe fallback mode when no LLM API KEY is available or LLM fails.
    """
    tool_calls_made = []

    # Detect invoice_id in message or find top overdue invoice
    target_inv = None
    for token in user_message.replace(",", " ").replace(":", " ").replace("?", " ").replace("!", " ").split():
        clean_token = token.strip("?.!,:;\"'")
        if clean_token.startswith("INV"):
            target_inv = clean_token
            break

    ranked = rank_invoices(invoices_df, customers_df)
    tool_calls_made.append({
        "tool_name": "rank_invoices",
        "input": {"min_tier": "high_priority"},
        "result": {"total_ranked": len(ranked)}
    })

    if not target_inv and not ranked.empty:
        target_inv = str(ranked.iloc[0]["invoice_id"])
    elif not target_inv:
        target_inv = "INV001184"

    prof = execute_agent_tool("get_customer_profile", {"invoice_id": target_inv}, invoices_df, customers_df)
    tool_calls_made.append({
        "tool_name": "get_customer_profile",
        "input": {"invoice_id": target_inv},
        "result": prof
    })

    opt_res = execute_agent_tool("optimize_offer", {"invoice_id": target_inv}, invoices_df, customers_df)
    tool_calls_made.append({
        "tool_name": "optimize_offer",
        "input": {"invoice_id": target_inv},
        "result": opt_res
    })

    best = opt_res.get("best_offer")
    
    # Explicit Intent Check for Payment Link Creation in Fallback Mode
    msg_lower = user_message.lower()
    requests_payment_link = any(kw in msg_lower for kw in ["create", "generate", "send", "payment link", "pay link", "execute"])

    if fallback_reason == "NO_API_KEY":
        tag = "[Deterministic Fallback Mode (No LLM Key)]"
    elif fallback_reason == "GEMINI_API_ERROR":
        tag = f"[Deterministic Fallback Mode (Gemini API Error: {error_details or '503/Quota'})]"
    elif fallback_reason == "ANTHROPIC_API_ERROR":
        tag = f"[Deterministic Fallback Mode (Anthropic API Error: {error_details or 'Unavailable'})]"
    else:
        tag = "[Deterministic Fallback Mode]"

    if best and requests_payment_link:
        plink = execute_agent_tool("create_payment_link", {"invoice_id": target_inv, "offer_amount": best["offer_amount"]}, invoices_df, customers_df)
        tool_calls_made.append({
            "tool_name": "create_payment_link",
            "input": {"invoice_id": target_inv, "offer_amount": best["offer_amount"]},
            "result": plink
        })

        narration = (
            f"{tag}\n"
            f"Analyzed invoice {target_inv} for customer {prof['customer_id']} (Original Amount: ₹{prof['invoice_amount']:,.2f}, Recovery Score: {prof['recovery_score']:.4f}).\n"
            f"Evaluated {opt_res['candidates_evaluated']} candidate offers against merchant floor ₹{opt_res['merchant_floor']:,.2f}.\n"
            f"Selected optimal offer: ₹{best['offer_amount']:,.2f} ({best['discount_pct']}% discount, {best['days_to_payment']}-day terms) "
            f"with predicted acceptance probability {best['acceptance_probability']*100:.2f}% yielding Expected Value ₹{best['expected_value']:,.2f}.\n"
            f"Created Razorpay Test Payment Link: {plink['payment_link_url']}"
        )
    elif best:
        narration = (
            f"{tag}\n"
            f"Analyzed invoice {target_inv} for customer {prof['customer_id']} (Original Amount: ₹{prof['invoice_amount']:,.2f}, Recovery Score: {prof['recovery_score']:.4f}).\n"
            f"Evaluated {opt_res['candidates_evaluated']} candidate offers against merchant floor ₹{opt_res['merchant_floor']:,.2f}.\n"
            f"Recommended optimal offer: ₹{best['offer_amount']:,.2f} ({best['discount_pct']}% discount, {best['days_to_payment']}-day terms) "
            f"with predicted acceptance probability {best['acceptance_probability']*100:.2f}% yielding Expected Value ₹{best['expected_value']:,.2f}.\n"
            f"(Payment link was not generated as execution was not requested)."
        )
    else:
        narration = f"{tag} Analyzed invoice {target_inv}. No valid offer satisfied the merchant floor constraint."

    return {
        "status": "success",
        "final_response": narration,
        "tool_calls_made": tool_calls_made,
        "turns_used": len(tool_calls_made),
        "is_fallback": True,
        "fallback_reason": fallback_reason
    }


def run_negotiator_agent(user_message: str, invoices_df: pd.DataFrame, customers_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Real LLM Tool-Calling Negotiator Agent using Google Gemini API (gemini-3.7-flash) with fallback.
    """
    gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    anthropic_key = ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")

    if not gemini_key and not anthropic_key:
        print("[AGENT-BRAIN] No LLM API KEY found. Using safe deterministic fallback mode.")
        return run_deterministic_fallback(user_message, invoices_df, customers_df)

    # 1. Primary LLM Provider: Google Gemini API (gemini-3.7-flash)
    if gemini_key and HAS_GEMINI_SDK:
        try:
            client = genai.Client(api_key=gemini_key)

            system_instruction = (
                "You are the Revenue Rescue Negotiator Agent, an AI financial recovery assistant.\n"
                "Your objective is to help merchants investigate overdue invoices, analyze recoverability, and optimize recovery offers.\n"
                "STRICT ACTION GATING RULE:\n"
                "- NEVER call 'create_payment_link' UNLESS the user explicitly asks to create, generate, send, or execute a payment link.\n"
                "- If the user only asks for analysis, recommendations, or best offers, evaluate customer profile and optimal offer without creating a payment link.\n"
                "STRICT FINANCIAL SAFETY RULES:\n"
                "1. NEVER calculate or invent invoice amounts, discount amounts, merchant floors, acceptance probabilities, or expected values yourself.\n"
                "2. ALWAYS call backend tools ('rank_invoices', 'get_customer_profile', 'optimize_offer', 'create_payment_link') to obtain deterministic mathematical calculations.\n"
                "3. Explain the returned numbers accurately to the user.\n"
                "4. NEVER create a payment link without first executing optimize_offer to verify the merchant floor and valid offer amount."
            )

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=GEMINI_TOOLS,
                temperature=0.0
            )

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_message)]
                )
            ]

            tool_calls_made = []
            turns = 0

            while turns < MAX_TOOL_ITERATIONS:
                turns += 1
                response = client.models.generate_content(
                    model="gemini-3.7-flash",
                    contents=contents,
                    config=config
                )

                function_calls = response.function_calls

                if function_calls:
                    if response.candidates and response.candidates[0].content:
                        contents.append(response.candidates[0].content)

                    func_response_parts = []
                    for call in function_calls:
                        tool_name = call.name
                        tool_args = dict(call.args) if call.args else {}

                        # Execute tool deterministically in backend
                        tool_res = execute_agent_tool(tool_name, tool_args, invoices_df, customers_df)

                        tool_calls_made.append({
                            "tool_name": tool_name,
                            "input": tool_args,
                            "result": tool_res
                        })

                        func_response_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response=tool_res
                            )
                        )

                    contents.append(
                        types.Content(
                            role="user",
                            parts=func_response_parts
                        )
                    )
                else:
                    final_text = response.text or ""
                    return {
                        "status": "success",
                        "provider": "gemini",
                        "model": "gemini-3.7-flash",
                        "final_response": final_text,
                        "tool_calls_made": tool_calls_made,
                        "turns_used": turns,
                        "is_fallback": False
                    }

            return run_deterministic_fallback(user_message, invoices_df, customers_df, fallback_reason="GEMINI_API_ERROR")

        except Exception as err:
            print(f"[AGENT-BRAIN] Gemini LLM execution error: {err}. Falling back to deterministic mode.")
            err_msg = str(err)
            short_err = "503/High Demand" if "503" in err_msg or "UNAVAILABLE" in err_msg else ("Quota/Rate Limit" if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg else "API Error")
            return run_deterministic_fallback(user_message, invoices_df, customers_df, fallback_reason="GEMINI_API_ERROR", error_details=short_err)

    # 2. Secondary Migration Provider: Anthropic API
    elif anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            system_prompt = (
                "You are the Revenue Rescue Negotiator Agent, an AI financial recovery assistant.\n"
                "Your objective is to help merchants investigate overdue invoices, analyze recoverability, and optimize recovery offers.\n"
                "STRICT ACTION GATING RULE:\n"
                "- NEVER call 'create_payment_link' UNLESS the user explicitly asks to create, generate, send, or execute a payment link.\n"
                "- If the user only asks for analysis, recommendations, or best offers, evaluate customer profile and optimal offer without creating a payment link.\n"
                "STRICT FINANCIAL SAFETY RULES:\n"
                "1. NEVER calculate or invent invoice amounts, discount amounts, merchant floors, acceptance probabilities, or expected values yourself.\n"
                "2. ALWAYS call backend tools ('rank_invoices', 'get_customer_profile', 'optimize_offer', 'create_payment_link') to obtain deterministic mathematical calculations.\n"
                "3. Explain the returned numbers accurately to the user.\n"
                "4. NEVER create a payment link without first executing optimize_offer to verify the merchant floor and valid offer amount."
            )

            messages = [{"role": "user", "content": user_message}]
            tool_calls_made = []
            turns = 0

            while turns < MAX_TOOL_ITERATIONS:
                turns += 1
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    system=system_prompt,
                    tools=AGENT_TOOLS,
                    messages=messages
                )

                if response.stop_reason == "tool_use":
                    assistant_content = response.content
                    messages.append({"role": "assistant", "content": assistant_content})

                    tool_results_content = []
                    for block in assistant_content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            tool_res = execute_agent_tool(tool_name, tool_input, invoices_df, customers_df)

                            tool_calls_made.append({
                                "tool_name": tool_name,
                                "input": tool_input,
                                "result": tool_res
                            })

                            tool_results_content.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps(tool_res)
                            })

                    messages.append({"role": "user", "content": tool_results_content})

                elif response.stop_reason in ["end_turn", "max_tokens"]:
                    final_text = ""
                    for block in response.content:
                        if getattr(block, "type", None) == "text":
                            final_text += block.text

                    return {
                        "status": "success",
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet-20241022",
                        "final_response": final_text,
                        "tool_calls_made": tool_calls_made,
                        "turns_used": turns,
                        "is_fallback": False
                    }
                else:
                    break

            return run_deterministic_fallback(user_message, invoices_df, customers_df)

        except Exception as err:
            print(f"[AGENT-BRAIN] Anthropic LLM execution error: {err}. Falling back to deterministic mode.")
            return run_deterministic_fallback(user_message, invoices_df, customers_df)

    else:
        return run_deterministic_fallback(user_message, invoices_df, customers_df)
