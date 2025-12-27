import React, { useEffect, useMemo, useState } from "react";
import NewsAnnotationTool from "./website_management/pages/NewsAnnotationTool.js";

// 15-minute global timer (shown on intro video screen + main tool)
const TASK_TIMER_SECONDS = 15 * 60;

function formatTimeMMSS(totalSeconds) {
  const s = Math.max(0, Number(totalSeconds) || 0);
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(Math.floor(s % 60)).padStart(2, "0");
  return `${mm}:${ss}`;
}

function App() {
  const [timeLeftSeconds, setTimeLeftSeconds] = useState(TASK_TIMER_SECONDS);

  useEffect(() => {
    if (timeLeftSeconds <= 0) return;

    const id = window.setInterval(() => {
      setTimeLeftSeconds((t) => (t > 0 ? t - 1 : 0));
    }, 1000);

    return () => window.clearInterval(id);
  }, [timeLeftSeconds]);

  const timeExpired = timeLeftSeconds <= 0;
  const timeLabel = useMemo(() => formatTimeMMSS(timeLeftSeconds), [timeLeftSeconds]);

  return (
    <div className="text-center">
      {/* Header (always visible) */}
      <h1 className="text-2xl font-bold mt-4">News Annotation Tool</h1>

      {/* Global timer: visible on the intro video screen AND the main annotation UI */}
      <div className="mt-3 inline-flex flex-col items-center justify-center px-4 py-2 rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="text-xs font-semibold tracking-wide text-gray-600">Time remaining</div>
        <div
          className={`mt-1 text-2xl font-extrabold tabular-nums ${
            timeLeftSeconds <= 60 ? "text-red-600" : "text-gray-900"
          }`}
          aria-live="polite"
        >
          {timeExpired ? "00:00" : timeLabel}
        </div>
        <div className="mt-2 text-xs text-gray-600 leading-relaxed max-w-md">
          if you are unable to complete the task within this time you will be unable to submit your completion code on MTurk
        </div>
        {timeExpired && (
          <div className="mt-2 text-xs font-semibold text-red-600" role="status">
            Time expired — you can no longer submit.
          </div>
        )}
      </div>

      {/* Pass timer state down so the tool can disable submission/actions when expired */}
      <NewsAnnotationTool timeLeftSeconds={timeLeftSeconds} timeExpired={timeExpired} />
    </div>
  );
}

export default App;
