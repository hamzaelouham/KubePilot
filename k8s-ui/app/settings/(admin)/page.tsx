import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsOverviewPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Centralized configuration</CardTitle>
              <CardDescription className="mt-1 max-w-2xl">
                Settings modules will be delivered incrementally while bootstrap infrastructure configuration remains managed by Kubernetes.
              </CardDescription>
            </div>
            <Badge variant="secondary">Admin only</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-muted-foreground">
            No runtime settings are editable yet. This protected area is ready for General, Appearance, provider, model, integration, credential, and audit modules.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
