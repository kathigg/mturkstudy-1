import React from "react";
import NewsAnnotationTool from "./website_management/pages/NewsAnnotationTool.js";
import instructionVid from "./Videos/Instruction-Video.mov";

function App() {
  return (
    <div className="text-center">
      
      <h1 className="text-2xl font-bold mt-4">News Annotation Tool</h1>
      <video
        src={instructionVid}
        controls
        autoPlay
        muted
        playsInline
        width="600"
        height="300"
        className="block mx-auto"
      />
      
      <NewsAnnotationTool />
    </div>
  );
}

export default App;
