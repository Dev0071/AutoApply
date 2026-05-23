const COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  queued: "bg-blue-100 text-blue-700",
  running: "bg-yellow-100 text-yellow-800",
  review: "bg-purple-100 text-purple-800",
  submitted: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
