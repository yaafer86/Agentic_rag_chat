import { create } from "zustand";

type WorkspaceState = {
  currentId: string | null;
  setCurrent: (id: string | null) => void;
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  currentId: localStorage.getItem("workspace_id"),
  setCurrent: (id) => {
    if (id) localStorage.setItem("workspace_id", id);
    else localStorage.removeItem("workspace_id");
    set({ currentId: id });
  },
}));
