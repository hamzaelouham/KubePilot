"use client";

import { useMemo, useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AssistantModel } from "@/lib/assistant/models";

export function AssistantModelSelector({
  models,
  value,
  disabled,
  onChange,
}: {
  models: AssistantModel[];
  value?: string;
  disabled?: boolean;
  onChange: (modelId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = models.find((model) => model.id === value);
  const groups = useMemo(() => {
    const byProvider = new Map<string, { name: string; models: AssistantModel[] }>();
    for (const model of models) {
      const group = byProvider.get(model.provider_id) ?? { name: model.provider_name, models: [] };
      group.models.push(model);
      byProvider.set(model.provider_id, group);
    }
    return [...byProvider.entries()];
  }, [models]);

  return (
    <ModelSelector open={open} onOpenChange={setOpen}>
      <ModelSelectorTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            disabled={disabled || models.length === 0}
            aria-label="Select AI model"
            aria-expanded={open}
          />
        }
      >
        <span className="max-w-48 truncate">{selected?.friendly_name ?? "Select model"}</span>
        <ChevronsUpDown data-icon="inline-end" />
      </ModelSelectorTrigger>
      <ModelSelectorContent title="Select an AI model" className="sm:max-w-lg">
        <ModelSelectorInput placeholder="Search models…" />
        <ModelSelectorList>
          <ModelSelectorEmpty>No eligible models found.</ModelSelectorEmpty>
          {groups.map(([providerId, group]) => (
            <ModelSelectorGroup key={providerId} heading={group.name}>
              {group.models.map((model) => (
                <ModelSelectorItem
                  key={model.id}
                  value={model.id}
                  keywords={[model.friendly_name, model.external_model_id, model.provider_name]}
                  data-checked={model.id === value}
                  onSelect={() => {
                    onChange(model.id);
                    setOpen(false);
                  }}
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <ModelSelectorName>{model.friendly_name}</ModelSelectorName>
                    <span className="truncate text-xs text-muted-foreground">{model.external_model_id}</span>
                  </span>
                  <span className="flex gap-1">
                    {model.capabilities.streaming ? <Badge variant="outline">Streaming</Badge> : null}
                    {model.capabilities.tools ? <Badge variant="outline">Tools</Badge> : null}
                  </span>
                </ModelSelectorItem>
              ))}
            </ModelSelectorGroup>
          ))}
        </ModelSelectorList>
      </ModelSelectorContent>
    </ModelSelector>
  );
}
