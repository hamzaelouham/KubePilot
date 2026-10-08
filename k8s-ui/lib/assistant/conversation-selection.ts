export function conversationIdToLoad(activeId: string | undefined, loadedId: string | undefined) {
  return activeId && activeId !== loadedId ? activeId : undefined;
}

export function isConversationSelectionCurrent(activeId: string | undefined, conversationId: string) {
  return activeId === conversationId;
}
