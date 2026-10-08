"use client";

import { useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { agentRequest, agentSkillSchema, agentSkillWriteSchema, AgentRequestError, type AgentSkill, type AgentSkillWrite, type AgentTemplate } from "@/lib/assistant/agents";

const emptySkill: AgentSkillWrite = { name: "", description: "", instructions: "" };

export function SkillsCatalog({ skills, editable, onRefresh }: { skills: AgentSkill[]; editable: boolean; onRefresh: () => void }) {
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<AgentSkill | null | false>(false);
  const [draft, setDraft] = useState<AgentSkillWrite>(emptySkill);
  const [failure, setFailure] = useState<AgentRequestError | null>(null);
  const [pending, setPending] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AgentSkill | null>(null);
  const visible = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return skills.filter(skill => `${skill.name} ${skill.description}`.toLocaleLowerCase().includes(query));
  }, [skills, search]);

  function startNew() {
    setEditing(null); setDraft(emptySkill); setFailure(null);
  }
  function startEdit(skill: AgentSkill) {
    setEditing(skill); setDraft({ name: skill.name, description: skill.description, instructions: skill.instructions }); setFailure(null);
  }
  async function save() {
    const parsed = agentSkillWriteSchema.safeParse(draft);
    if (!parsed.success) {
      setFailure(new AgentRequestError(422, "validation_error", parsed.error.issues[0]?.message ?? "Check the skill fields."));
      return;
    }
    setPending(true); setFailure(null);
    try {
      await agentRequest(editing ? `/api/assistant/agents/skills/${editing.id}` : "/api/assistant/agents/skills", agentSkillSchema, editing ? "PUT" : "POST", parsed.data);
      setEditing(false); setDraft(emptySkill); onRefresh();
    } catch (error) {
      setFailure(error instanceof AgentRequestError ? error : new AgentRequestError(500, "unexpected_error", "Could not save the skill."));
    } finally { setPending(false); }
  }
  async function remove(skill: AgentSkill) {
    setPending(true); setFailure(null);
    try {
      await agentRequest(`/api/assistant/agents/skills/${skill.id}`, agentSkillSchema, "DELETE");
      if (editing && editing.id === skill.id) setEditing(false);
      onRefresh();
    } catch (error) {
      setFailure(error instanceof AgentRequestError ? error : new AgentRequestError(500, "unexpected_error", "Could not delete the skill."));
    } finally { setPending(false); }
  }

  return <div className="flex min-w-0 flex-col gap-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">Reusable skills</h2><p className="text-sm text-muted-foreground">Shared instruction blocks. Skills guide an agent but never grant permissions.</p></div>
      {editable && <Button onClick={startNew}><Plus data-icon="inline-start" />New skill</Button>}
    </div>
    {failure && <Alert variant="destructive"><AlertTitle>{failure.status === 409 ? "Skill cannot be changed" : failure.status === 403 ? "Access denied" : "Skill request failed"}</AlertTitle><AlertDescription>{failure.message}</AlertDescription></Alert>}
    {editing !== false && <Card>
      <CardHeader><CardTitle>{editing ? "Edit skill" : "New skill"}</CardTitle><CardDescription>Instruction text is escaped in the UI and treated as configuration, never executable code.</CardDescription></CardHeader>
      <CardContent className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium" htmlFor="skill-name">Name<Input id="skill-name" value={draft.name} disabled={pending} onChange={event => setDraft(previous => ({ ...previous, name: event.target.value }))} /></label>
        <label className="flex flex-col gap-1 text-sm font-medium" htmlFor="skill-description">Description<Input id="skill-description" value={draft.description} disabled={pending} onChange={event => setDraft(previous => ({ ...previous, description: event.target.value }))} /></label>
        <label className="flex flex-col gap-1 text-sm font-medium" htmlFor="skill-instructions">Instructions<Textarea id="skill-instructions" rows={6} value={draft.instructions} disabled={pending} onChange={event => setDraft(previous => ({ ...previous, instructions: event.target.value }))} /></label>
        <div className="flex flex-wrap justify-end gap-2"><Button variant="outline" disabled={pending} onClick={() => setEditing(false)}>Cancel</Button><Button disabled={pending} onClick={() => void save()}>{pending ? "Saving…" : editing ? "Save skill" : "Create skill"}</Button></div>
      </CardContent>
    </Card>}
    <Input aria-label="Search skills" placeholder="Search skills…" value={search} onChange={event => setSearch(event.target.value)} />
    {!visible.length ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">{skills.length ? "No skills match this search." : editable ? "Create a reusable skill for your team." : "No skills are configured yet."}</CardContent></Card> : <div className="grid gap-3 md:grid-cols-2">{visible.map(skill => <Card key={skill.id} className="min-w-0"><CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle className="break-words text-base">{skill.name}</CardTitle><CardDescription>{skill.description}</CardDescription></div><Badge variant="outline">{skill.assigned_agent_count} agents</Badge></div></CardHeader><CardContent className="flex items-center justify-between gap-3"><p className="line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">{skill.instructions}</p>{editable && <div className="flex shrink-0 gap-1"><Button variant="ghost" size="icon" aria-label={`Edit ${skill.name}`} disabled={pending} onClick={() => startEdit(skill)}><Pencil /></Button><Button variant="ghost" size="icon" aria-label={`Delete ${skill.name}`} disabled={pending} onClick={() => setDeleteTarget(skill)}><Trash2 /></Button></div>}</CardContent></Card>)}</div>}
    <AlertDialog open={deleteTarget !== null} onOpenChange={open => { if (!open && !pending) setDeleteTarget(null); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {deleteTarget?.name}?</AlertDialogTitle>
          <AlertDialogDescription>Assigned agents must be updated first. This shared skill will be permanently deleted.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={pending} onClick={() => { if (!deleteTarget) return; const skill = deleteTarget; setDeleteTarget(null); void remove(skill); }}>Delete skill</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>;
}

export function TemplatesCatalog({ templates, editable, onUse }: { templates: AgentTemplate[]; editable: boolean; onUse: (template: AgentTemplate) => void }) {
  return <div className="flex min-w-0 flex-col gap-5">
    <div><h2 className="text-lg font-semibold">Agent templates</h2><p className="text-sm text-muted-foreground">Safe server-owned starting points. Choosing one fills a draft; it never saves or runs an agent.</p></div>
    {!templates.length ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No templates are available.</CardContent></Card> : <div className="grid gap-4 md:grid-cols-3">{templates.map(template => <Card key={template.id} className="flex min-w-0 flex-col"><CardHeader><CardTitle className="text-base">{template.name}</CardTitle><CardDescription>{template.description}</CardDescription></CardHeader><CardContent className="flex flex-1 flex-col gap-4"><p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{template.instructions}</p><div className="mt-auto flex flex-wrap gap-1">{template.tool_ids.map(tool => <Badge key={tool} variant="outline">{tool}</Badge>)}</div>{editable ? <Button onClick={() => onUse(template)}>Use template</Button> : <p className="text-xs text-muted-foreground">Only administrators can create shared agents.</p>}</CardContent></Card>)}</div>}
  </div>;
}
