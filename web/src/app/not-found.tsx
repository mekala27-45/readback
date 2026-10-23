import Link from "next/link";

export default function NotFound() {
  return (
    <div className="measure space-y-3">
      <h1 className="display text-3xl font-extrabold">Nothing reads back here</h1>
      <p className="text-ink2">That page does not exist. The desk is the place to start.</p>
      <Link prefetch={false} className="underline" href="/">
        Go to the desk
      </Link>
    </div>
  );
}
