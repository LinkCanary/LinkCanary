export default function Input({ label, error, className = '', ...props }) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <input
        className={`
          block w-full rounded-lg border px-4 py-2.5 text-gray-900
          placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500
          ${error ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300'}
        `}
        {...props}
      />
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

export function Select({ label, error, children, className = '', ...props }) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <select
        className={`
          block w-full rounded-lg border px-4 py-2.5 text-gray-900
          focus:outline-none focus:ring-2 focus:ring-blue-500
          ${error ? 'border-red-300' : 'border-gray-300'}
        `}
        {...props}
      >
        {children}
      </select>
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

export function Checkbox({ label, className = '', ...props }) {
  return (
    <label className={`flex items-center gap-2 ${className}`}>
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        {...props}
      />
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}
