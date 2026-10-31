"use client"; // This should be client-side

import { useMemo } from "react";
import { EventType } from "../types/EventType";

type Props = {
  events: EventType[];
  onSelect: (event: EventType, rect: DOMRect) => void;
}

const timeFormat = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
})

export default function TodayStrip({ events, onSelect }: Props) {
  const todaysEvents = useMemo(() => {
    const today = new Date().toDateString();
    return events
      .filter((event) => new Date(event.start_datetime).toDateString() === today)
      .sort((a, b) =>
        new Date(a.start_datetime).getTime() - new Date(b.start_datetime).getTime()
      );
  }, [events]);

  if (todaysEvents.length === 0) {
    return null;
  }

  return (
    <section className="my-3">
      <h2 className="mb-2 text-sm font-semibold text-gray-600 dark:text-gray-300">
        Happening today
      </h2>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {todaysEvents.map((event) => (
          <button
            key={event.id}
            onClick={(e) => onSelect(event, e.currentTarget.getBoundingClientRect())}
            className="shrink-0 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
          >
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {event.is_all_day ? "All day" : timeFormat.format(new Date(event.start_datetime))}
            </p>
            <p className="max-w-48 truncate text-sm dark:text-white">{event.title}</p>
            {event.location && (
              <p className="max-w-48 truncate text-xs text-gray-500 dark:text-gray-400">
                {event.location}
              </p>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}


    