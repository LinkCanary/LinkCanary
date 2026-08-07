import { Link } from 'react-router-dom';

/*
 * Inline upgrade prompt — shown when a user hits a plan limit.
 * Usage:
 *   <UpgradePrompt metric="crawls" limit={5} current={5} plan="hatchling" />
 */

const PAYMENT_LINKS = {
  songbird_monthly: '',
  songbird_yearly: '',
  flock_monthly: '',
  flock_yearly: '',
};

const PLAN_NAMES = {
  hatchling: 'Hatchling',
  songbird: 'Songbird',
  flock: 'Flock',
};

export default function UpgradePrompt({ metric, limit, current, plan = 'hatchling', compact = false }) {
  const nextPlan = plan === 'hatchling' ? 'songbird' : 'flock';

  const messages = {
    crawls: `You've used all ${limit} crawls this month.`,
    pages: `This site exceeds your ${limit.toLocaleString()} page limit.`,
    projects: `You've reached the ${limit} project limit.`,
    seats: `You've used all ${limit} team seats.`,
    export: 'This export format requires a higher plan.',
    retention: 'This report has expired on your current plan.',
  };

  const message = messages[metric] || `You've reached your ${metric} limit.`;

  if (compact) {
    return (
      <div className="flex items-center gap-3 p-3 bg-[#F5B800]/5 border border-[#F5B800]/20 rounded-xl">
        <span className="text-[#F5B800] text-lg">⚡</span>
        <p className="text-sm text-[#2B3A4A] dark:text-gray-300 flex-1">{message}</p>
        <Link
          to="/account/billing"
          className="shrink-0 px-3 py-1.5 bg-[#F5B800] hover:bg-[#e0a800] text-[#2B3A4A] text-sm font-bold rounded-lg transition-colors"
        >
          Upgrade
        </Link>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#232a3b] rounded-2xl border-2 border-[#F5B800]/30 p-6 max-w-md">
      <div className="flex items-start gap-3 mb-4">
        <span className="text-2xl">🐤</span>
        <div>
          <h3 className="font-bold text-[#2B3A4A] dark:text-white">{message}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Upgrade to <strong>{PLAN_NAMES[nextPlan]}</strong> for more capacity.
          </p>
        </div>
      </div>
      <div className="flex gap-3">
        <Link
          to="/account/billing"
          className="flex-1 py-2.5 bg-[#F5B800] hover:bg-[#e0a800] text-[#2B3A4A] font-bold rounded-xl text-center transition-colors"
        >
          View plans
        </Link>
      </div>
    </div>
  );
}
