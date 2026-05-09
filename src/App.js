
import NewsAnnotationTool from "./website_management/pages/NewsAnnotationTool.js";

// 15-minute global timer (shown on intro video screen + main tool)
//const TASK_TIMER_SECONDS = 15 * 60;

// function formatTimeMMSS(totalSeconds) {
//   const s = Math.max(0, Number(totalSeconds) || 0);
//   const mm = String(Math.floor(s / 60)).padStart(2, "0");
//   const ss = String(Math.floor(s % 60)).padStart(2, "0");
//   return `${mm}:${ss}`;
// }

function App() {

 



  return (
    <div className="text-center">
      {/* Header (always visible) */}
      <h1 className="text-2xl font-bold mt-4">News Annotation Tool</h1>


      {/* Pass timer state down so the tool can disable submission/actions when expired */}
      <NewsAnnotationTool />
    </div>
  );
}

export default App;
