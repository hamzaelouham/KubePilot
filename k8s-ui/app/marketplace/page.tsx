import { MarketplaceView } from "@/components/marketplace-view";
import { requireUsableBackendUser } from "@/lib/auth";

export default async function MarketplacePage() {
  const user = await requireUsableBackendUser();
  return <MarketplaceView user={user} />;
}