import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/*
 * Stripe Payment Links — configured in the Stripe dashboard.
 *
 * To set up:
 * 1. Go to https://dashboard.stripe.com/payment-links
 * 2. Create a Payment Link for each plan/period combo
 * 3. Add a metadata field: "org_id" (customer will fill this at checkout
 *    OR you pass it via client_reference_id in the URL)
 * 4. Set the success URL to: https://app.linkcanary.io/account/billing?upgraded=true
 * 5. Paste the links below
 *
 * Stripe Payment Links handle:
 * - The entire checkout UI (card, Apple Pay, Google Pay)
 * - Receipt emails
 * - Subscription creation
 * - Webhook events (invoice.paid, customer.subscription.updated)
 *
 * You only need the webhook handler on the backend to sync the plan state.
 */

const PAYMENT_LINKS = {
  songbird_monthly: 'https://buy.stripe.com/aFa28r6zUeOTeBx91VefC00',
  songbird_yearly: 'https://buy.stripe.com/4gMaEXaQa4afbpla5ZefC02',
  flock_monthly: 'https://buy.stripe.com/5kQbJ1cYigX18d93HBefC01',
  flock_yearly: 'https://buy.stripe.com/dRm6oH4rM8qvbpl1ztefC03',
};

const PLANS = [
  {
    id: 'hatchling',
    name: 'Hatchling',
    price: 'Free',
    period: '',
    description: 'Get started with link auditing',
    features: ['5 crawls/month', '500 pages per crawl', '7-day report retention', 'CSV export', '1 project'],
    cta: 'Current plan',
    highlight: false,
  },
  {
    id: 'songbird',
    name: 'Songbird',
    price: '$19',
    period: '/mo',
    yearly: '$190/yr',
    description: 'For freelancers and small sites',
    features: ['50 crawls/month', '5,000 pages per crawl', '90-day report retention', 'CSV, HTML, PDF, Excel export', '10 projects', '3 team seats', 'Slack & Discord webhooks', 'Staging auth (Basic)'],
    cta: 'Upgrade to Songbird',
    highlight: true,
    links: { monthly: 'songbird_monthly', yearly: 'songbird_yearly' },
  },
  {
    id: 'flock',
    name: 'Flock',
    price: '$49',
    period: '/mo',
    yearly: '$490/yr',
    description: 'For agencies and teams',
    features: ['Unlimited crawls', '50,000 pages per crawl', '1-year report retention', 'All export formats + Google Sheets', 'Unlimited projects', '15 team seats', 'API access', 'All webhook integrations', 'Semantic analysis', 'Priority support'],
    cta: 'Upgrade to Flock',
    highlight: false,
    links: { monthly: 'flock_monthly', yearly: 'flock_yearly' },
  },
];

export default function Billing() {
  const [searchParams] = useSearchParams();
  const [account, setAccount] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [billingPeriod, setBillingPeriod] = useState('monthly');

  useEffect(() => {
    Promise.all([
      fetch('/api/account/me', { credentials: 'include' }).then(r => r.json()),
      fetch('/api/account/usage', { credentials: 'include' }).then(r => r.json()),
      fetch('/api/account/subscription', { credentials: 'include' }).then(r => r.json()),
    ]).then(([me, us]) => {
      setAccount(me);
      setUsage(us);
      setLoading(false);
    });
  }, []);

  const handleUpgrade = (plan) => {
    const key = plan.links?.[billingPeriod];
    const url = PAYMENT_LINKS[key];
    if (!url) {
      alert('Payment not configured yet. Add your Stripe Payment Link URLs to enable upgrades.');
      return;
    }
    // Append client_reference_id so the webhook knows which org paid
    const separator = url.includes('?') ? '&' : '?';
    window.open(`${url}${separator}client_reference_id=${account?.org_id}`, '_blank');
  };

  const handleManage = async () => {
    try {
      const res = await fetch('/api/billing/portal', { method: 'POST', credentials: 'include' });
      const data = await res.json();
      if (data.portal_url) {
        window.location.href = data.portal_url;
      } else {
        alert('Billing portal not available yet. Configure Stripe to enable self-serve management.');
      }
    } catch {
      alert('Billing portal not available yet.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#F5B800]" />
      </div>
    );
  }

  const currentPlan = account?.plan || 'hatchling';

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {searchParams.get('upgraded') && (
        <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl text-green-700 dark:text-green-400">
          Upgrade successful! Your new plan is active.
        </div>
      )}

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[#2B3A4A] dark:text-white">Billing</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Manage your plan and usage</p>
      </div>

      {/* Current usage */}
      {usage && (
        <div className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 mb-8">
          <h2 className="font-semibold text-[#2B3A4A] dark:text-white mb-4">Current usage ({usage.period})</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500 dark:text-gray-400">Crawls</span>
                <span className="font-medium text-[#2B3A4A] dark:text-white">
                  {usage.usage.crawls} / {usage.limits.crawls_per_month || '∞'}
                </span>
              </div>
              <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#F5B800] rounded-full transition-all"
                  style={{
                    width: usage.limits.crawls_per_month
                      ? `${Math.min(100, (usage.usage.crawls / usage.limits.crawls_per_month) * 100)}%`
                      : '5%',
                  }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500 dark:text-gray-400">Max pages per crawl</span>
                <span className="font-medium text-[#2B3A4A] dark:text-white">
                  {usage.limits.max_pages_per_crawl?.toLocaleString() || '∞'}
                </span>
              </div>
            </div>
          </div>
          {currentPlan !== 'hatchling' && (
            <button onClick={handleManage} className="mt-4 text-sm text-[#F5B800] hover:underline font-medium">
              Manage subscription →
            </button>
          )}
        </div>
      )}

      {/* Billing period toggle */}
      <div className="flex justify-center mb-8">
        <div className="bg-gray-100 dark:bg-[#1a1f2e] rounded-xl p-1 flex">
          <button
            onClick={() => setBillingPeriod('monthly')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              billingPeriod === 'monthly'
                ? 'bg-white dark:bg-[#232a3b] text-[#2B3A4A] dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingPeriod('yearly')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              billingPeriod === 'yearly'
                ? 'bg-white dark:bg-[#232a3b] text-[#2B3A4A] dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            Yearly <span className="text-green-500 text-xs">Save 17%</span>
          </button>
        </div>
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PLANS.map((plan) => {
          const isCurrent = plan.id === currentPlan;
          return (
            <div
              key={plan.id}
              className={`relative bg-white dark:bg-[#232a3b] rounded-2xl border-2 p-6 flex flex-col ${
                plan.highlight
                  ? 'border-[#F5B800] shadow-lg'
                  : 'border-gray-100 dark:border-gray-700'
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#F5B800] text-[#2B3A4A] text-xs font-bold px-3 py-1 rounded-full">
                  Most popular
                </div>
              )}
              <h3 className="text-lg font-bold text-[#2B3A4A] dark:text-white">{plan.name}</h3>
              <div className="mt-2">
                <span className="text-3xl font-bold text-[#2B3A4A] dark:text-white">
                  {billingPeriod === 'yearly' && plan.yearly ? plan.yearly : plan.price}
                </span>
                {plan.period && billingPeriod === 'monthly' && (
                  <span className="text-gray-400 text-sm">{plan.period}</span>
                )}
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-4">{plan.description}</p>
              <ul className="space-y-2 flex-1 mb-6">
                {plan.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#2B3A4A] dark:text-gray-300">
                    <span className="text-[#F5B800] mt-0.5">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <button disabled className="w-full py-3 bg-gray-100 dark:bg-gray-700 text-gray-400 rounded-xl font-medium cursor-default">
                  Current plan
                </button>
              ) : plan.id === 'hatchling' ? (
                <button disabled className="w-full py-3 bg-gray-100 dark:bg-gray-700 text-gray-400 rounded-xl font-medium cursor-default">
                  Free forever
                </button>
              ) : (
                <button
                  onClick={() => handleUpgrade(plan)}
                  className={`w-full py-3 rounded-xl font-bold transition-colors ${
                    plan.highlight
                      ? 'bg-[#F5B800] hover:bg-[#e0a800] text-[#2B3A4A]'
                      : 'bg-[#2B3A4A] hover:bg-[#1e2a38] text-white dark:bg-[#F5B800] dark:hover:bg-[#e0a800] dark:text-[#2B3A4A]'
                  }`}
                >
                  {plan.cta}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Payment info */}
      <p className="text-center text-sm text-gray-400 mt-8">
        Payments securely handled by Stripe. Cancel anytime.
      </p>
    </div>
  );
}
