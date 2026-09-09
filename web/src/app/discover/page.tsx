import { PageHeader } from "@/components/shared/page-header";
import { DiscoveryForm } from "@/components/discovery/discovery-form";

export default function DiscoverPage() {
  return (
    <div>
      <PageHeader
        title="Discover"
        description="Create a discovery job. It runs asynchronously; you'll be taken to a live monitor."
      />
      <DiscoveryForm />
    </div>
  );
}
