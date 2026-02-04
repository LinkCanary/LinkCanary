export default function Card({ children, className = '' }) {
  return (
    <div className={`bg-white dark:bg-dark/80 rounded-xl shadow-sm border border-dark/10 dark:border-primary/20 ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 border-b border-dark/10 dark:border-primary/20 ${className}`}>
      {children}
    </div>
  );
}

export function CardBody({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 ${className}`}>
      {children}
    </div>
  );
}
