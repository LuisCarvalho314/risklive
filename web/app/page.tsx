//© 2025 University of Aberdeen. All rights reserved


import { redirect } from "next/navigation";

// Execute the redirect at request time so the production server emits Location.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  redirect("/topics");
}
