export function conversationIdToLoad(activeId: string | undefined, loadedId: string | undefined) {
  return activeId && activeId !== loadedId ? activeId : undefined;
}
