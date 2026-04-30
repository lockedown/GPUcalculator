import { redirect } from "next/navigation";

// `/compare` was a near-duplicate of the dashboard. Kept as a permanent
// redirect to preserve any existing bookmarks / external links.
export default function ComparePage(): never {
  redirect("/");
}
