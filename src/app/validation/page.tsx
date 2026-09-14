import ValidationHub, { type ValidationTab } from "./ValidationHub";

const allowedTabs: ValidationTab[] = ["scenario", "trace", "evaluation"];

export default async function ValidationPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const params = await searchParams;
  const initialTab = allowedTabs.includes(params.tab as ValidationTab) ? params.tab as ValidationTab : "scenario";
  return <ValidationHub initialTab={initialTab} />;
}
