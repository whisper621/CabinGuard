import { redirect } from "next/navigation";

export default function EvaluationPage() {
  redirect("/validation?tab=evaluation");
}
