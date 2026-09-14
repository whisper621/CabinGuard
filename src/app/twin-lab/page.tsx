import { redirect } from "next/navigation";

export default function TwinLabPage() {
  redirect("/validation?tab=scenario");
}
