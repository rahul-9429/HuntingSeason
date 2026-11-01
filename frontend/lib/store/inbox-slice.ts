import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { InboxFilter } from "@/lib/types";

interface InboxState {
  filter: InboxFilter;
  query: string;
}

const initialState: InboxState = { filter: "all", query: "" };

export const inboxSlice = createSlice({
  name: "inbox",
  initialState,
  reducers: {
    setFilter: (state, action: PayloadAction<InboxFilter>) => {
      state.filter = action.payload;
    },
    setQuery: (state, action: PayloadAction<string>) => {
      state.query = action.payload;
    },
  },
});

export const { setFilter, setQuery } = inboxSlice.actions;
