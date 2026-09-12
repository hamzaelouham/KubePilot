import { MarketplaceView } from "@/components/marketplace-view";
import { requireUsableBackendUser } from "@/lib/auth";
import { fetchInitialMarketplaceData } from "@/lib/marketplace-server";

export default async function MarketplacePage() {
  const user = await requireUsableBackendUser();
  const initialData = await fetchInitialMarketplaceData();
  return <MarketplaceView user={user} initialData={initialData} />;
}
