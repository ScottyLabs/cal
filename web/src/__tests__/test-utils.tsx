// src/__tests__/test-utils.tsx
import { GcalEventsProvider } from "../context/GCalEventsContext";
import { EventStateProvider } from "../context/EventStateContext";
import { UserProvider } from "../context/UserContext";

// Same nesting as the providers in src/app/layout.tsx.
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <GcalEventsProvider>
      <EventStateProvider>
        <UserProvider>{children}</UserProvider>
      </EventStateProvider>
    </GcalEventsProvider>
  );
}
