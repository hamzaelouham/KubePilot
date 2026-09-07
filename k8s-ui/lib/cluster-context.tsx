"use client";

import { createContext, useContext } from "react";

export const ClusterContext = createContext<string>("");

export function useCluster(): string {
  return useContext(ClusterContext);
}