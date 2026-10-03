'use client';
import { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "./AuthContext";
import { EventType } from "../app/types/EventType";
import { EventInput } from "@fullcalendar/core";
import { List } from "lucide-react";
import { API_BASE_URL } from "~/app/utils/api/api";
import { useGcalEvents } from "./GCalEventsContext";
import { CategoryOrg } from "~/app/utils/types";

export type ModalView = "details" | "update" | "pre_upload" | "upload" | "uploadLink" | null;
type Tag = { id?: number; name: string };

type ModalData = {
  savedEventDetails?: EventType;
  eventInfo?: EventType;
  selectedTags?: Tag[];
  selectedCategory?: CategoryOrg;
  eventType?: string;
};

export type PopoverPosition = {
  x: number;
  y: number;
  anchorRect: DOMRect;
} | null;

type EventStateContextType = {
  selectedEvent: number|null;
  setSelectedEvent: (id: number|null) => void;
  modalView: ModalView;
  setModalView: (view: ModalView) => void;
  modalData: ModalData;
  setModalData: (data: ModalData) => void;
  savedEventIds: Set<number>;
  toggleAdded: (event: EventType) => Promise<void>;
  calendarEvents: EventInput[];
  setCalendarEvents: (events: EventInput[]) => void;
  popoverPosition: PopoverPosition;
  setPopoverPosition: (position: PopoverPosition) => void;
};

export const EventStateContext = createContext<EventStateContextType | null>(null);

export const EventStateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isSignedIn } = useAuth();
  const { isGoogleConnected, cmuCalendarId } = useGcalEvents();
  const [selectedEvent, setSelectedEvent] = useState<number|null>(null);
  const [modalView, setModalView] = useState<ModalView>(null);
  const [modalData, setModalData] = useState<ModalData>({});
  const [savedEventIds, setSavedEventIds] = useState(new Set<number>());
  const [calendarEvents, setCalendarEvents] = useState<EventInput[]>([]);
  const [popoverPosition, setPopoverPosition] = useState<PopoverPosition>(null); 

  // console.log("😮Fetching saved events for user:", user?.id);

  // fetch saved events IDs on login
  useEffect(() => {
    if (!isSignedIn) return;
    async function fetchSaved() {
      try {
        // console.log("😮Fetching saved events for user:", user?.id);
        const response = await axios.get<number[]>(`${API_BASE_URL}/events/user_saved_events`, {
          withCredentials: true,
        });
        setSavedEventIds(new Set(response.data));
        console.log("😄Saved Event IDs: ", response.data)
      } catch (err) {
        console.error("😔Error loading saved events", err);
      }
    }
    void fetchSaved();
  }, [isSignedIn]);


  // TODO: define toggleAdded (move it here)
  const toggleAdded = async (event: EventType) => {
      // const updatedEvents = [...events];
      // const index = updatedEvents.findIndex((e) => e.id === thisId);
      // const event = updatedEvents[index];

    if (!event) return;
    const isCurrentlySaved = savedEventIds.has(event.id)

    console.log("👀toggling event, ", savedEventIds.has(event.id), event);

    // 1. Toggle locally - update attribute
    // event.user_saved = !event.user_saved;
    // setEvents(updatedEvents);
    if (isCurrentlySaved) {
      // Remove the event from the saved IDs Set
      setSavedEventIds(prevSet => {
        const newSet = new Set(prevSet);
        newSet.delete(event.id)
        return newSet
      })
      console.log("(remove) updated saved ids: ", savedEventIds)
    } else {
      // Add the event to saved Ids Set
      setSavedEventIds(prevSet => new Set(prevSet).add(event.id))
      console.log("(add) updated saved ids: ", savedEventIds)
    }
    
    console.log("❓❓❓id in saved set? ", savedEventIds.has(event.id))

    // 2. Update the User_saved_events table in database
    try {
      if (!isCurrentlySaved) {
        // Add the event to current user's calendar
        await axios.post(`${API_BASE_URL}/events/user_saved_events`, {
          event_id: event.id,
          google_event_id: event.id, // [Q|TODO] is google event id needed in this table
        }, {
          withCredentials: true,
        }); 
      } else {
        // Remove the event from current user's calendar
        await axios.delete(`${API_BASE_URL}/events/user_saved_events/${event.id}`, {
          data: {
          google_event_id: event.id, // [Q|TODO] is google event id needed in this table
        },
          withCredentials: true,
        });
      }
    } catch (err) {
      console.error("Error saving / unsaving the event to user_saved_events, ", err);
    }

    // 3. Update calendar view
    // fetchCalendarEvents();

    // 4. Sync with Google Calendar (only if connected)
    if (isGoogleConnected) {
      try {
        if (!isCurrentlySaved) {
          console.log("Adding event to Google Calendar");
          // Add to Google Calendar via backend
          await axios.post(`${API_BASE_URL}/google/calendar/events/add`, {
            local_event_id: event.id,
            title: event.title,
            start: event.start_datetime,
            end: event.end_datetime,
            location: event.location,
            description: event.description,
          }, {
            withCredentials: true,
          });        
        } else {
          // Remove from Google Calendar via backend
          await axios.delete(`${API_BASE_URL}/google/calendar/events/${event.id}`, {
            withCredentials: true,
          });
        }
      } catch (err) {
        console.error("Error syncing with Google Calendar:", err);
        // Optionally show user-friendly error
        const action = isCurrentlySaved ? "remove from" : "add to";
        console.warn(`Failed to ${action} Google Calendar. Event saved locally only.`);
      }
    } else {
      console.log("Google Calendar not connected. Event saved locally only.");
    }
  };



  return (
    <EventStateContext.Provider value={{
        selectedEvent, setSelectedEvent,
        modalView, setModalView,
        modalData, setModalData,
        savedEventIds,
        toggleAdded,
        calendarEvents, setCalendarEvents,
        popoverPosition, setPopoverPosition
      }}>
        {children}
      </EventStateContext.Provider>
  )
}


export const useEventState = () => {
  const context = useContext(EventStateContext);
  if (!context) {
    throw new Error("useEventState must be used within a EventStateContext.Provider");
  }

  const openDetails = (event_id: number, savedEventDetails?: EventType, position?: PopoverPosition) => {
    context.setSelectedEvent(event_id);
    context.setModalData({"savedEventDetails": savedEventDetails});
    context.setPopoverPosition(position ?? null);
    context.setModalView("details");
  };
  const openUpdate = (eventInfo: EventType, selectedTags: Tag[]) => {
    // context.setSelectedEvent(event_id);// no need since always routed from the details modal
    
    context.setModalData({"eventInfo": eventInfo, "selectedTags": selectedTags})
    console.log("opening update.... setting modal data", eventInfo)
    context.setModalView("update");
  };
  const openPreUpload = () => {
    context.setSelectedEvent(null);
    context.setModalView("pre_upload");
  }
  const openUploadLink = (selectedCategory: CategoryOrg) => {
    // context.setSelectedEvent(null); // no need since always routed from pre-upload
    context.setModalData({"selectedCategory": selectedCategory})
    // need to add modalData
    context.setModalView("uploadLink");
  };
  const openUpload = (selectedCategory: CategoryOrg, eventType: string) => {
    // context.setSelectedEvent(null); // no need since always routed from pre-upload
    context.setModalData({"selectedCategory": selectedCategory, "eventType": eventType})
    context.setModalView("upload");
  };
  
  const closeModal = () => {
    context.setSelectedEvent(null);
    context.setModalView(null);
    context.setPopoverPosition(null);
  };
  


  return {
    selectedEvent: context.selectedEvent,
    modalView: context.modalView,
    modalData: context.modalData,
    savedEventIds: context.savedEventIds,
    toggleAdded: context.toggleAdded,
    calendarEvents: context.calendarEvents,
    setCalendarEvents: context.setCalendarEvents,
    popoverPosition: context.popoverPosition,
    openDetails,
    openUpdate,
    openPreUpload,
    openUpload,
    openUploadLink,
    closeModal
  }
};