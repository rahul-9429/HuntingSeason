import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { useDispatch, useSelector } from "react-redux";
import { contactsSlice } from "@/lib/store/contacts-slice";
import { inboxSlice } from "@/lib/store/inbox-slice";

const rootReducer = combineReducers({
  contacts: contactsSlice.reducer,
  inbox: inboxSlice.reducer,
});

export function makeStore() {
  return configureStore({ reducer: rootReducer });
}

export type RootState = ReturnType<typeof rootReducer>;
export type AppStore = ReturnType<typeof makeStore>;
export type AppDispatch = AppStore["dispatch"];

export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
