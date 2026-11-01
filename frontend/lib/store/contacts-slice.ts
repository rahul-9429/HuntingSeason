import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ContactFilter } from "@/lib/types";

interface ContactsState {
  type: ContactFilter;
  pitchContactId: string | null;
}

const initialState: ContactsState = { type: "all", pitchContactId: null };

export const contactsSlice = createSlice({
  name: "contacts",
  initialState,
  reducers: {
    setType: (state, action: PayloadAction<ContactFilter>) => {
      state.type = action.payload;
    },
    openPitch: (state, action: PayloadAction<string>) => {
      state.pitchContactId = action.payload;
    },
    closePitch: (state) => {
      state.pitchContactId = null;
    },
  },
});

export const { setType, openPitch, closePitch } = contactsSlice.actions;
