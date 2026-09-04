// API Fetch Utility Wrappers for API-CORE backend endpoints
const DEFAULT_PROD_URL = 'https://razorpay-revenue-rescue.onrender.com';
const DEFAULT_LOCAL_URL = 'http://127.0.0.1:8000';

function getBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return DEFAULT_PROD_URL;
  }
  return DEFAULT_LOCAL_URL;
}

const BASE_URL = getBaseUrl();

async function fetchJSON(url, options = {}) {
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      throw new Error(errorBody.detail || `HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error [${url}]:`, err);
    throw err;
  }
}

export async function getHealth() {
  return fetchJSON(`${BASE_URL}/health`);
}

export async function getDashboardSummary() {
  return fetchJSON(`${BASE_URL}/dashboard/summary`);
}

export async function getOpportunities(topN = 5) {
  return fetchJSON(`${BASE_URL}/opportunities?top_n=${topN}`);
}

export async function getInvoices(tier = 'high_priority', minAmount = 0) {
  return fetchJSON(`${BASE_URL}/invoices?tier=${tier}&min_amount=${minAmount}`);
}

export async function getInvoiceDetail(invoiceId) {
  return fetchJSON(`${BASE_URL}/invoices/${invoiceId}`);
}

export async function recommendRecoveryOffer(invoiceId, merchantFloor) {
  return fetchJSON(`${BASE_URL}/recovery/${invoiceId}/recommend`, {
    method: 'POST',
    body: JSON.stringify({ merchant_floor: merchantFloor }),
  });
}

export async function executeRecoveryOffer(invoiceId, offerAmount) {
  return fetchJSON(`${BASE_URL}/recovery/${invoiceId}/execute`, {
    method: 'POST',
    body: JSON.stringify({ offer_amount: offerAmount }),
  });
}

export async function getInvoiceAuditTrail(invoiceId) {
  return fetchJSON(`${BASE_URL}/invoices/${invoiceId}/audit-trail`);
}

export async function triggerMockWebhook(invoiceId, amount) {
  return fetchJSON(`${BASE_URL}/webhooks/razorpay`, {
    method: 'POST',
    body: JSON.stringify({ invoice_id: invoiceId, amount: amount }),
  });
}

export async function askAgent(message) {
  return fetchJSON(`${BASE_URL}/agent/ask`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
