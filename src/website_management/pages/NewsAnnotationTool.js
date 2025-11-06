import React, { useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CardContent } from "../components/CardContent";
import Papa from "papaparse";

import { database, ref, push } from "../../firebaseConfig";
import { get, update, runTransaction } from "firebase/database";
import instructionVid from "../../Videos/Instruction-Video.mov";


function IntroScreen({ onDone }) {
  const [videoReady, setVideoReady] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [watchedEnough, setWatchedEnough] = useState(false);
  const videoRef = useRef(null);
  const watchedSecondsRef = useRef(new Set());
  const [showNoPolarizingPopup, setShowNoPolarizingPopup] = useState(false);
const [pendingNoPolarizingConfirm, setPendingNoPolarizingConfirm] = useState(false);

  const handleTimeUpdate = () => {
    const v = videoRef.current;
    if (!v) return;
    const t = Math.floor(v.currentTime);
    watchedSecondsRef.current.add(t);
    if (videoDuration > 0) {
      const ratio = watchedSecondsRef.current.size / Math.max(1, Math.floor(videoDuration));
      if (ratio >= 0.98) setWatchedEnough(true);
    }
  };

  const handleLoadedMeta = () => {
    const v = videoRef.current;
    if (!v) return;
    setVideoDuration(v.duration || 0);
    setVideoReady(true);
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gray-100">
      <div className="w-full max-w-3xl bg-white rounded-xl shadow p-6">
        <h1 className="text-2xl font-bold text-center mb-4">
          Video Tool Guide (Please watch before continuing)
        </h1>

        <video
          ref={videoRef}
          src={instructionVid}
          controls
          playsInline
          className="block mx-auto w-full rounded-lg"
          onLoadedMetadata={handleLoadedMeta}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setWatchedEnough(true)}
        />

        
        <div className="mt-6 flex justify-center">
          <button
            className={
              watchedEnough
                ? "px-5 py-2 rounded text-white bg-blue-600 hover:bg-blue-700"
                : "px-5 py-2 rounded text-white bg-gray-400 cursor-not-allowed"
            }
            disabled={!watchedEnough}
            onClick={onDone}
          >
            Next: Start the Annotation Tool
          </button>
        </div>

        <p className="mt-3 text-xs text-center text-gray-500">
          You must watch the full video before continuing.
        </p>
      </div>
    </div>
  );
}

// --- Selection constraints ---
const MIN_WORDS = 4;
const MAX_WORDS = 25;

const countWords = (t = "") => (t.trim() ? t.trim().split(/\s+/).length : 0);


// Utility to fix misencoded characters, where any characters not from English
// would be changed through UTF-8 encoding, leaving characters like é mangled as √©. 
// The CSV file is already encoded incorrectly, so this code is trying to fix that. 
// adds paragraph breaks after 100 words. 
function paragraphAdd(text) {
  const words = text.split(/\s+/);
  const paragraphs = [];
  let paragraph = "";
  let wordCount = 0;
  let insideQuote = false;

  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    paragraph += word + " ";
    wordCount++;

    // Detect quote entry/exit
    if (word.includes('"')) {
      const quoteCount = (word.match(/"/g) || []).length;
      // Toggle quote status for each odd quote encountered
      if (quoteCount % 2 !== 0) {
        insideQuote = !insideQuote;
      }
    }

    // Only insert break if:
    // - 150+ words
    // - Ends with a period
    // - Not inside a quote
    if (wordCount >= 150 && word.endsWith(".") && !insideQuote) {
      paragraphs.push(paragraph.trim());
      paragraph = "";
      wordCount = 0;
    }
  }

  if (paragraph.trim()) {
    paragraphs.push(paragraph.trim());
  }

  return paragraphs;
}
// loops through the title and capitalizes all non-conjunction words
function titleCapitalization(title){ 
  const titleWords = title.split(" ");
  const conjunctions = ["a", "to", "off", "over", "from", "into", "with", "yet", "so", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of", "on", "or", "the", "up"];
  for (let i = 0; i < titleWords.length; i++) {
    if (!(conjunctions.includes(titleWords[i]))){
      // if the title word is not a conjunction, make it caps 
      titleWords[i] = titleWords[i].charAt(0).toUpperCase() + titleWords[i].slice(1);
    }
  }
  return titleWords.join(" ");

}

// Function to shuffle array randomly
const shuffleArray = (array) => {
  return array.sort(() => Math.random() - 0.5);
};

const DropdownItem = ({ icon, title, children, openTitle, setOpenTitle, color }) => {
  const isOpen = openTitle === title;
  const handleClick = () => setOpenTitle(isOpen ? null : title);

  const borderColor =
    color === "yellow"
      ? "border-yellow-400"
      : color === "red"
      ? "border-red-400"
      : "border-blue-400";

  return (
    <div
      className={`mb-3 rounded-lg transition-all duration-300 ${
        isOpen
          ? `bg-white/70 ${borderColor} border-l-4 shadow-sm`
          : "hover:bg-gray-50"
      }`}
    >
      <button
        onClick={handleClick}
        className="flex items-center justify-between w-full text-left text-base font-semibold text-gray-900 hover:text-blue-600 focus:outline-none px-2 py-2"
      >
        <span className="flex items-center space-x-2">
          {icon && <span>{icon}</span>}
          <span>{title}</span>
        </span>
        <span
          className={`text-xl leading-none transition-transform duration-300 ${
            isOpen ? "rotate-90 text-blue-500" : "rotate-0 text-gray-500"
          }`}
        >
          {isOpen ? "−" : "+"}
        </span>
      </button>

      {isOpen && (
        <div className="mt-2 ml-3 mr-2 text-left text-gray-800 transition-all duration-300 space-y-2 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
};


function ToolMain() {
    console.log("YAY Loaded NewsAnnotationTool");
    const [openDropdown, setOpenDropdown] = useState(null); 
    const [showNoPolarizingPopup, setShowNoPolarizingPopup] = useState(false);
    const [pendingNoPolarizingConfirm, setPendingNoPolarizingConfirm] = useState(false);
    const [completionCode, setCompletionCode] = useState("");
    const [allArticles, setAllArticles] = useState([]);
    const [articles, setArticles] = useState([]);
    const [currentArticleIndex, setCurrentArticleIndex] = useState(0);
    const [annotations, setAnnotations] = useState({});
    const [selectedText, setSelectedText] = useState("");
    const [textAnnotations, setTextAnnotations] = useState({});
    const [selectedCategory, setSelectedCategory] = useState("");
    const [selectedSubcategory, setSelectedSubcategory] = useState("");
    const [showRightInstructions, setShowRightInstructions] = useState(true);
    const [wordCount, setWordCount] = useState(0);
    const [selectedIdx, setSelectedIdx] = useState(null);


    const handleCategoryButtonClick = (categoryKey) => {
      const wc = countWords(selectedText);
    
      // For all categories except "No_Polarizing_Language", enforce the word-count rule
      if (categoryKey !== "No_Polarizing_Language" && (wc < MIN_WORDS || wc > MAX_WORDS)) {
        alert(`Please select between ${MIN_WORDS} and ${MAX_WORDS} words before annotating.`);
        return;
      }
    
      setSelectedCategory(categoryKey);
      setSelectedSubcategory("");
    
      // Trigger popup overlay for "No polarizing language"
      if (categoryKey === "No_Polarizing_Language") {
        setPendingNoPolarizingConfirm(true);
        setShowNoPolarizingPopup(true);
        return;
      }
    
      // Regular categories behave normally
    };
    

    // Live word count only
useEffect(() => {
  const handleSelectionChange = () => {
    const selection = window.getSelection();
    setWordCount(countWords(selection.toString().trim()));
  };

  document.addEventListener("selectionchange", handleSelectionChange);
  return () => document.removeEventListener("selectionchange", handleSelectionChange);
}, []);

    const categoryOptions = {
      Persuasive_Propaganda: ["Exaggeration", "Slogans", "Bandwagon", "Casual Oversimplification", "Doubt"],
      Inflammatory_Language: ["Demonization", "Name-Calling", "Scapegoating"],
      "No_Polarizing_Language": ["No polarizing language"],
  };

    const [showSurvey, setShowSurvey] = useState(false);
    const [surveyResponses, setSurveyResponses] = useState({});
    const [confidence, setConfidence] = useState(0);
    const [bias, setBias] = useState(0);
    const [openFeedback, setOpenFeedback] = useState("");
    const [showThankYou, setShowThankYou] = useState(false);

    const articleId = articles[currentArticleIndex]?.id;
  
    const countCharacters = (text) => {
      return text.trim().length;
    };

const autoSaveAnnotation = (category, subcategory) => {
  if (category && subcategory && articleId) {
    // For "no polarizing language", we don't require selected text
    const textToSave = category === "No_Polarizing_Language" 
      ? "no polarizing language selected" 
      : selectedText;
    
    if (category === "No_Polarizing_Language" || selectedText) {
      setTextAnnotations((prevAnnotations) => ({
        ...prevAnnotations,
        [articleId]: [
          ...(prevAnnotations[articleId] || []),
          { title: articles[currentArticleIndex]?.title || "", 
            text: textToSave, 
            category, 
            subcategory },
        ],
      }));
      
      setSelectedText("");
      setSelectedCategory("");
      setSelectedSubcategory("");
    }
  }
};

// Update category and subcategory selection handlers
const handleCategoryChange = (e) => {
  const newCategory = e.target.value;
  setSelectedCategory(newCategory);
  if (selectedSubcategory && (selectedText || newCategory === "No_Polarizing_Language")) {
    autoSaveAnnotation(newCategory, selectedSubcategory);
  }
};

const handleSubcategoryChange = (e) => {
  const newSubcategory = e.target.value;
  setSelectedSubcategory(newSubcategory);
  if (selectedCategory && (selectedText || selectedCategory === "No_Polarizing_Language")) {
    autoSaveAnnotation(selectedCategory, newSubcategory);
  }
};

// Update JSX for annotation inputs
<select
  className="p-2 border border-gray-300 rounded-md mb-2"
  value={selectedCategory}
  onChange={handleCategoryChange}
>
  <option value="">Select a Category</option>
  {Object.keys(categoryOptions).map((category) => (
    <option key={category} value={category}>
      {category}
    </option>
  ))}
</select>

{selectedCategory && Array.isArray(categoryOptions[selectedCategory]) && (
  <select
    className="p-2 border border-gray-300 rounded-md mb-2"
    value={selectedSubcategory}
    onChange={handleSubcategoryChange}
  >
    <option value="">Select a Subcategory</option>
    {categoryOptions[selectedCategory].map((subcategory) => (
      <option key={subcategory} value={subcategory}>
        {subcategory}
      </option>
    ))}
  </select>
)}


    const downloadAnnotations = (annotations, textAnnotations, surveyResponses) => {
        const articleTitles = articles.map((article) => ({
            id: article.id,
            title: titleCapitalization(articles.title), //applies capitalization to each article
        }));
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-");

        const data = {
          annotations,
          textAnnotations,
          surveyResponses,
          articleTitles,
          timestamp: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `annotations_${timestamp}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
  };
      
    

    // RANDOM ARTICLE SELECTION (COMMENTED OUT)
    // useEffect(() => {
    //     setArticles(shuffleArray([...sampleArticles]));
    // }, []);

    // function getThreeUniqueInts() {
    //   const numbers = new Set();
    
    //   while (numbers.size < 3) {
    //     const rand = Math.floor(Math.random() * (552 - 2 + 1)) + 2;
    //     numbers.add(rand); // Set ensures uniqueness
    //   }
    
    //   return Array.from(numbers);
    // }

    // console.log(getThreeUniqueInts());

    // const dict = {};
    // for (let i = 2; i <= 552; i++) {
    //   dict[i.toString()] = 0;
    // }

    // console.log(dict);

    // const testRef = ref(database, "test");
    // push(testRef, dict)
    //   .then(() => {
    //     console.log("Test data saved to Firebase");
    //   })
    //   .catch((error) => {
    //     console.error("Error saving to Firebase:", error);
    //   });


    // const submissionsRef = ref(database, "submissions");
    // push(submissionsRef, data)
    //   .then(() => {
    //     console.log("Submission saved to Firebase");
    //   })
    //   .catch((error) => {
    //     console.error("Error saving to Firebase:", error);
    //   });

    

    // HARD-CODED ARTICLE SELECTION


    
    // ORIGINAL RANDOM SELECTION (COMMENTED OUT)
    /*
    useEffect(() => {
        fetch("/new_filtered_news_300_700_words.csv")
        .then((response) => response.text())
        .then((csvText) => {
          Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            complete: function (results) {
              const parsedArticles = results.data.map((item, index) => ({
                id: index + 1,
                title: item["Headline"],
                content: item["News body"],
            }));
            const randomArticles = shuffleArray(parsedArticles).slice(0, 3);
            setArticles(randomArticles);
            },
          });
        });
    }, []);
    */
    /*
        setArticles(shuffleArray([...sampleArticles.slice(0, 3)]));
      }, []);
    */

const MAX_PER_ARTICLE = 3;
async function pickAndClaimIndex() {
  const usageRef = ref(database, "articleUsage");
  const claimedRef = ref(database, "claimedArticles");

  const [usageSnap, claimedSnap] = await Promise.all([get(usageRef), get(claimedRef)]);
  let usage = usageSnap.exists() ? usageSnap.val() : {};
  let claimed = claimedSnap.exists() ? claimedSnap.val() : {};

  // Initialize first 12 indices to 0 if missing
  for (let i = 0; i < 12; i++) {
    if (usage[i] === undefined) usage[i] = 0;
    if (claimed[i] === undefined) claimed[i] = 0;
  }

  // Candidates must be under both caps
  const candidates = Object.keys(usage)
    .map(Number)
    .filter((i) => usage[i] < MAX_PER_ARTICLE && (claimed[i] ?? 0) < MAX_PER_ARTICLE);

  if (candidates.length === 0) {
    console.warn("No available articles left.");
    return null;
  }

  // Try in random order; atomically claim the first that succeeds
  const shuffled = candidates.sort(() => Math.random() - 0.5);
  for (const i of shuffled) {
    const ok = await tryClaimIndex(i);
    if (ok) {
      console.log(`Chosen & claimed index: ${i}`);
      return i;
    }
  }

  console.warn("All candidates were claimed concurrently. Try again.");
  return null;
}

// Atomically try to claim an index: increment claimedArticles[i] iff it's < MAX_PER_ARTICLE
async function tryClaimIndex(i) {
  const idxRef = ref(database, `claimedArticles/${i}`);
  const result = await runTransaction(idxRef, (curr) => {
    const v = curr ?? 0;
    if (v >= MAX_PER_ARTICLE) return; // abort transaction
    return v + 1;                      // commit v+1
  });
  return result.committed; // true if we successfully claimed
}

// Decrement claim counter (never below 0)
async function unclaimArticle(i) {
  const idxRef = ref(database, `claimedArticles/${i}`);
  await runTransaction(idxRef, (curr) => {
    const v = curr ?? 0;
    return v > 0 ? v - 1 : 0;
  });
}

// Use transactions for logging usage too (safer under contention)
async function logArticleUsage(index) {
  const usageIdxRef = ref(database, `articleUsage/${index}`);
  await runTransaction(usageIdxRef, (curr) => (curr ?? 0) + 1);
  console.log(`Logged usage for index ${index}.`);
}

  useEffect(() => {
  fetch("/article_dataset_versions/test3_encoding_fixed_300_700_words.csv")
    .then((response) => response.text())
    .then(async (csvText) => {
      Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        complete: async function (results) {
          const parsedArticles = results.data.map((item, index) => ({
            id: index + 1,
            title: item["Headline"],
            content: item["News body"],
          }));
          setAllArticles(parsedArticles);

          const idx = await pickAndClaimIndex();
          if (idx !== null) {
            setSelectedIdx(idx);             // remember chosen index
            setArticles([parsedArticles[idx]]);
          }
        },
      });
    });
}, []);
  

const handleNextArticle = async () => {
  console.log("ARTICLE LENGTH:", articles.length);
  if (articles.length > 1) {
    return;
  }

  if (showSurvey) {
    // validate survey responses
    if (confidence === 0 || bias === 0 || openFeedback.trim() === "") {
      alert("Please answer all survey questions before continuing.");
      return;
    }

    const articleId = articles[currentArticleIndex]?.id;
    const annotationsForArticle = textAnnotations[articleId] || [];

    // Check if "no polarizing language" has been selected
    const hasNoPolarizingLanguage = annotationsForArticle.some(
      (a) =>
        a.category === "No_Polarizing_Language" &&
        a.subcategory === "no polarizing language"
    );

    if (annotationsForArticle.length === 0 && !hasNoPolarizingLanguage) {
      alert(
        "Please annotate at least one phrase or select 'no polarizing language' before continuing."
      );
      return;
    }

    const anyInvalid = annotationsForArticle.some(
      (a) => !a.category || !a.subcategory
    );

    if (anyInvalid) {
      alert("Each annotation must include a category and subcategory.");
      return;
    }

    // Save survey responses
    setSurveyResponses((prev) => ({
      ...prev,
      [articleId]: { confidence, bias, openFeedback },
    }));

    // reset survey UI state
    setSelectedText("");
    setSelectedCategory("");
    setSelectedSubcategory("");
    setShowSurvey(false);
    setConfidence(0);
    setBias(0);
    setOpenFeedback("");

    // If user already did 1 article, log usage now and show thank-you
    if (articles.length >= 1) {
      try {
        if (selectedIdx !== null) {
          await logArticleUsage(selectedIdx); // <-- increment only on Finish
          await unclaimArticle(selectedIdx);
        }
      } catch (e) {
        console.error("Failed to log article usage:", e);
      }
      console.log("User has completed 1 articles this session.");
      setShowThankYou(true);
      return;
    } else {
      // Otherwise fetch another article; remember index but log on that article's Finish
      const nextIdx = await pickAndClaimIndex();
      if (nextIdx !== null && allArticles[nextIdx]) {
        setSelectedIdx(nextIdx);
        setArticles((prev) => [...prev, allArticles[nextIdx]]);
        setCurrentArticleIndex((prev) => prev + 1);
      } else {
        // If Firebase runs out before 1, then show thank-you
        setShowThankYou(true);
      }
    }
  } else {
    // flip to survey view
    setShowSurvey(true);
  }
};

    

    const handleAnnotation = (label) => {
        const articleId = articles[currentArticleIndex]?.id;
        if (!articleId) return;

        setAnnotations((prevAnnotations) => ({
            ...prevAnnotations,
            [articleId]: label,
        }));

        alert(`Article labeled as: ${label}`);
    };

    const handleTextSelection = () => {
        const selection = window.getSelection();
        if (selection.toString().trim() !== "") {
            setSelectedText(selection.toString().trim());
        }
    };

    const handleTextAnnotation = () => {
        if (selectedCategory && selectedSubcategory && (selectedText || selectedCategory === "No_Polarizing_Language")) {
            const articleId = articles[currentArticleIndex]?.id;
            const textToSave = selectedCategory === "No_Polarizing_Language" 
              ? "no polarizing language selected" 
              : selectedText;
            
            setTextAnnotations((prevAnnotations) => ({
                ...prevAnnotations,
                [articleId]: [
                    ...(prevAnnotations[articleId] || []),
                    { title: articles[currentArticleIndex]?.title || "", 
                      text: textToSave, 
                      category: selectedCategory, 
                      subcategory: selectedSubcategory },
                ],
            }));
            setSelectedText("");
            setSelectedCategory("");
            setSelectedSubcategory("");
        } else {
            alert("Please select a high-level category and a subcategory.");
        }
    };

    const handleRemoveAnnotation = (articleId, index) => {
        setTextAnnotations((prevAnnotations) => {
            const updatedAnnotations = [...(prevAnnotations[articleId] || [])];
            updatedAnnotations.splice(index, 1);
            return {
                ...prevAnnotations,
                [articleId]: updatedAnnotations,
            };
        });
    };

    

    // useEffect(() => {
    //     if (showThankYou) {
    //       downloadAnnotations(annotations, textAnnotations, surveyResponses);
    //     }
    //   }, [showThankYou]);
    const generateCode = () => `MTURK-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

    useEffect(() => {
        if (showThankYou) {

          const code = generateCode();
          setCompletionCode(code);
            const articleTitles = articles.map((article) => ({
                id: article.id,
                title: article.title,
            }))
          const data = {
            annotations,
            textAnnotations,
            surveyResponses,
            articleTitles,
            timestamp: new Date().toISOString(),
            completionCode,
          };
    
          const submissionsRef = ref(database, "submissions");
          push(submissionsRef, data)
            .then(() => {
              console.log("Submission saved to Firebase");
            })
            .catch((error) => {
              console.error("Error saving to Firebase:", error);
            });
        }
      }, [showThankYou]);

    

      
      return (
        <div className="flex w-full justify-center items-start min-h-screen bg-gray-100 relative">
          {/* --- No Polarizing Language Confirmation Overlay --- */}
          {showNoPolarizingPopup && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm transition-opacity duration-300">
              <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center animate-fadeIn">
                <h2 className="text-2xl font-bold mb-3 text-gray-900">Are you sure?</h2>
                <p className="text-sm text-gray-700 mb-6 leading-relaxed">
                  Selecting this option will trigger a closer review of your work.
                  <br /><br />
                  If the article truly contains <em>no polarizing language</em>,
                  click <strong>“I’m sure.”</strong> Otherwise, review the text again before submitting.
                </p>
      
                <div className="flex justify-center space-x-4">
                <Button
                  onClick={() => {
                    // Close popup
                    setShowNoPolarizingPopup(false);
                    setPendingNoPolarizingConfirm(false);

                    // Clear any "No Polarizing Language" selection
                    if (selectedCategory === "No_Polarizing_Language") {
                      setSelectedCategory("");
                      setSelectedSubcategory("");
                    }
                  }}
                  className="bg-gray-400 hover:bg-gray-500 text-white px-4 py-2 rounded"
                >
                  Cancel
                </Button>
                  <Button
                    onClick={() => {
                      const articleId = articles[currentArticleIndex]?.id;
                      if (articleId) {
                        setTextAnnotations((prev) => ({
                          ...prev,
                          [articleId]: [
                            ...(prev[articleId] || []),
                            {
                              title: articles[currentArticleIndex]?.title || "",
                              text: "No polarizing language selected",
                              category: "No_Polarizing_Language",
                              subcategory: "no polarizing language",
                            },
                          ],
                        }));
                      }
                      setShowNoPolarizingPopup(false);
                      setPendingNoPolarizingConfirm(false);
                    }}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded"
                  >
                    I’m sure
                  </Button>
                </div>
              </div>
            </div>
          )}
          
            {/* Instructions Sidebar */}
            <div className={`w-1/4 p-4 bg-gray-200 shadow-md transition-all duration-300 ${showRightInstructions ? "visible opacity-100 pointer-events-auto" : "invisible opacity-0 pointer-events-none"}`}>
                <h3 className="text-lg font-bold mb-2">Annotation Guide</h3>
                <p className="text-sm mb-2">Use the following categories for labeling:</p>

      {/* Persuasive Propaganda Section */}
<div className="bg-yellow-100 p-4 rounded mb-4">
  <strong className="text-yellow-700 text-center block mb-4 text-lg font-semibold">
    Persuasive Propaganda
  </strong>

  <DropdownItem title="Exaggeration" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="yellow">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        When something is made to sound artificially much bigger, better, or worse
        than it really is — or, the opposite, made to sound smaller or less serious
        than it actually is.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“A local protest ignited waves of outrage and sent shockwaves through the nation.”</li>
          <li>“This minor disagreement has become a national catastrophe, easily the worst of the modern era.”</li>
          <li>“The present scandal is nothing — just political theater — and most Americans aren’t even aware of it.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Slogans" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="yellow">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        A short, memorable phrase used to spark emotion or support a cause.
        Slogans simplify complex ideas into a few words and can promote unity,
        nationalism, or other sentiments. They can be positive or negative in tone.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“Make America Great Again” / “America First”</li>
          <li>“No Justice, No Peace”</li>
          <li>“Occupy Wall Street — We Are the 99%”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Bandwagon" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="yellow">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        When people are told to support something just because “everyone else”
        already supports it. The message is: if many others believe it, you should too.
        This relies on social pressure and popularity, not evidence.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“Most Americans back this plan, polls show.”</li>
          <li>“As the Senator emphasized, ‘every true Republican supports this cause.’”</li>
          <li>“No serious economist still believes raising taxes is a good idea.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Casual Oversimplification" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="yellow">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        When a complex issue is blamed on just one cause or explained with one
        simple answer, ignoring all the other factors that are probably involved.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“The media is the only reason the nation is divided.”</li>
          <li>“Inflation rose solely because of the president’s policies.”</li>
          <li>“Crime is up because of progressive prosecutors.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Doubt" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="yellow">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        Language that tries to make the audience question whether a person,
        group, or institution is competent, honest, or legitimate.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“Is he really ready to be the Mayor?”</li>
          <li>“Is this leader even capable of running the country?”</li>
          <li>“Some experts question whether the agency’s data can be trusted.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>
</div>

{/* Inflammatory Language Section */}
<div className="bg-red-100 p-4 rounded mb-6">
  <strong className="text-red-700 text-center block mb-4 text-lg font-semibold">
    Inflammatory Language
  </strong>

  <DropdownItem title="Name-Calling" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="red">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        Using a loaded positive or negative label to shape how the audience feels
        about a person, group, or idea. Instead of giving evidence, the speaker
        uses emotionally charged wording to discredit or glorify.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“The movement, composed largely of radical extremists, has demanded sweeping reform.”</li>
          <li>“Big-money interests continue to profit during the crisis.”</li>
          <li>“The oft-labeled terrorist sympathizers took to the streets in the latest wave of protests.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Demonization" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="red">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        Describing people or groups as evil, dangerous, corrupt, disgusting,
        or less than human. The goal is to turn the audience against the target
        by making them sound like a threat to society.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“The nation’s bureaucrats are bleeding taxpayers dry.”</li>
          <li>“Migrants are parasites stealing American jobs.”</li>
          <li>“These politicians are eating away at the heart of this nation from within.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>

  <DropdownItem title="Scapegoating" openTitle={openDropdown} setOpenTitle={setOpenDropdown} color="red">
    <div className="mt-2 ml-4 text-left text-gray-800 space-y-2 py-3">
      <p className="text-base leading-relaxed">
        Blaming an entire group for a broad problem or crisis. The group is
        framed as the main cause of widespread harm or decline. This is almost
        always aimed at groups (not individuals) and links them to larger
        social, economic, or moral problems.
      </p>
      <div className="text-sm leading-relaxed text-gray-700">
        <p className="font-semibold">Examples:</p>
        <ul className="list-disc list-outside ml-5 space-y-1">
          <li>“The rising rents — driven as always by greedy landlords — represent a severe strain on families.”</li>
          <li>“Teachers’ unions are the reason kids are failing in school.”</li>
          <li>“Homelessness continues to rise because city officials refuse to enforce basic laws.”</li>
        </ul>
      </div>
    </div>
  </DropdownItem>
</div>
                
                <h3 className="text-lg font-bold mb-2">Video Tool Guide</h3>
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
            
                <Button onClick={() => 
                  setShowRightInstructions(false)} className="bg-gray-600 text-white w-full">Close Guide</Button>
            </div>
            

            {/* Main Content */}
            <div className="w-3/4 max-w-2xl bg-white p-6 rounded-lg shadow-md text-center">
                <Button onClick={() => setShowRightInstructions(!showRightInstructions)} className="bg-blue-600 text-white mb-4">
                    {showRightInstructions ? "Hide Instructions" : "Show Instructions"}
                </Button>
                {articles.length > 0 && (
                    <Card>
                        <h2 className="text-xl font-bold text-gray-900 mb-2">
                          {/*Calls the article capitalization function*/}
                            {titleCapitalization(articles[currentArticleIndex]?.title)}
                        </h2>
                        <CardContent>
                        {paragraphAdd(articles[currentArticleIndex]?.content).map((para, idx) => (
  <p key={idx} className="text-gray-700 mb-4" onMouseUp={handleTextSelection}>
    {para}
  </p>
))}
                        </CardContent>
                    </Card>
                )}

                {/* Annotation Buttons */}
                <div className="mt-4 flex justify-center space-x-4">
                    <Button onClick={() => handleCategoryButtonClick("Inflammatory_Language")} className="bg-red-500">
                      Inflammatory Language
                    </Button>
                    <Button onClick={() => handleCategoryButtonClick("Persuasive_Propaganda")} className="!bg-yellow-500">
                        Persuasive Propaganda
                    </Button>
                    <Button onClick={() => handleCategoryButtonClick("No_Polarizing_Language")} className="!bg-emerald-700/60">
                        No polarizing language
                    </Button>
                </div>


{selectedText &&  (
  <div className="mt-4 flex flex-col items-center">
   {/* Old code that displays selected text and word count above annotation buttons
   
   <p className="text-sm text-gray-700 mb-2">
      Selected Text: "{selectedText}"
    </p>
    {wordCount > 0 && (
    <p
      className={`text-xs mb-2 ${
        wordCount < MIN_WORDS || wordCount > MAX_WORDS
          ? "text-red-600"
          : "text-green-600"
      }`}
    >
      Word Count: {wordCount} (must be {MIN_WORDS}–{MAX_WORDS})
    </p>
   )} */}
    <select
      className="p-2 border border-gray-300 rounded-md mb-2"
      value={selectedCategory}
      onChange={handleCategoryChange}
    >
      <option value="">Select a Category</option>
      {Object.keys(categoryOptions).map((category) => (
        <option key={category} value={category}>
          {category}
        </option>
      ))}
    </select>
{selectedCategory && categoryOptions[selectedCategory] && (
  <select
    className="p-2 border border-gray-300 rounded-md mb-2"
    value={selectedSubcategory}
    onChange={handleSubcategoryChange}
  >
    <option value="">Select a Subcategory</option>
    {categoryOptions[selectedCategory].map((subcategory) => (
      <option key={subcategory} value={subcategory}>
        {subcategory}
      </option>
    ))}
  </select>
)}
  </div>
)}

{/* Display Saved Annotations */}
{textAnnotations[articles[currentArticleIndex]?.id]?.length > 0 && (
  <div className="mt-6 bg-gray-100 p-4 rounded-md">
    <h3 className="text-lg font-semibold">Annotated Text Excerpts:</h3>
    {textAnnotations[articles[currentArticleIndex]?.id].map((annotation, index) => (
      <div key={index} className="flex justify-between items-center mt-2">
        <p className="text-sm text-red-600">
          "{annotation.text}" – {annotation.category} → {annotation.subcategory}
        </p>
        <Button
          onClick={() => handleRemoveAnnotation(articles[currentArticleIndex]?.id, index)}
          className="bg-gray-400 text-white text-xs px-2 py-1 rounded"
        >
          Remove
        </Button>
      </div>
    ))}
  </div>
)}


            {/* Survey Form */}
        {showSurvey ? (
          <div className="mt-8 text-left">
            <h3 className="text-lg font-semibold mb-2">🧠 Post-Annotation Survey</h3>

            <label className="block mt-4">1. How confident are you that there is polarizing language (either persuasive propaganda or inflammatory language) in this article?</label>
            <div className="mt-2 space-y-1">
  {[1, 2, 3, 4, 5].map((val) => (
    <label key={val} className="block text-sm">
      <input
        type="radio"
        name="confidence"
        value={val}
        checked={confidence === val}
        onChange={() => setConfidence(val)}
        className="mr-2"
      />
      {val} – {["Not at all confident", "Slightly confident", "Moderately confident that there is polarizing language", "Very confident that there is polarizing language", "Extremely confident that there is polarizing language"][val - 1]}
    </label>
  ))}
</div>

            <label className="block mt-4">2. To what extent is the article misleading or biased?</label>
            <div className="mt-2 space-y-1">
  {[1, 2, 3, 4, 5].map((val) => (
    <label key={val} className="block text-sm"> 
      <input
        type="radio"
        name="bias"
        value={val}
        checked={bias === val}
        onChange={() => setBias(val)}
        className="mr-2"
      />
      {val} – {["Not at all", "Slightly", "Moderately", "Very much", "Extremely"][val - 1]}
    </label>
  ))}
</div>

<label className="block mt-4">
  3. Why did you tag this way? What specific phrases, tone choices, or examples made it stand out to you? You might reference particular sentences, framing choices, or emotional wording that influenced your decision.
</label>
<p className="text-sm text-gray-600 mb-1">
  Word count: {countCharacters(openFeedback)} (minimum 100 characters)
</p>
<textarea
  value={openFeedback}
  onChange={(e) => setOpenFeedback(e.target.value)}
  rows={6}
  className="w-full p-2 border rounded"
  placeholder="For example: “I tagged the phrase ‘reckless and corrupt regime’ as inflammatory because it uses strong language to attack without evidence."
></textarea>

<Button
  onClick={handleNextArticle}
  className="mt-4 bg-green-600 text-white"
  disabled={
    confidence === 0 ||
    bias === 0 ||
    countCharacters(openFeedback) < 100
  }
>
  {currentArticleIndex < articles.length - 1
    ? "Submit Survey & Load Next Article"
    : "Finish"}
</Button>
          </div>
        ) : (
          <div className="mt-6">
            <Button onClick={handleNextArticle} className="bg-blue-500">Submit</Button>
          </div>
        )}
            </div>


{/* Instructions Panel on Right */}
<div className={`w-1/4 p-4 bg-blue transition-all duration-300 ${showRightInstructions ? "visible opacity-100 pointer-events-auto" : "invisible opacity-0 pointer-events-none"}`}>
    <h3 className="text-lg font-bold mb-3">Instructions</h3>
    <p className="text-sm ml-3 text-left">
    You will annotate <strong>3 news articles</strong>. For each article, please follow these steps:
  </p>
  <div className="h-4 text-left" />
  <div className="h-4 text-left" />
  <ul className="list-decimal text-left ml-5 list-inside text-sm space-y-1">
    <li>
      <strong>Highlight a section of text</strong> between 4 and 25 words that you want to annotate.
    </li>
    <div className="h-3" />
    <li>
      Scroll down and <strong>select a category</strong> using either the buttons or the dropdown menu (e.g., <em>Flame Rhetoric</em> or <em>Persuasive Propaganda</em>).
    </li>
    <div className="h-3" />
    <li>
      <strong>Choose a subcategory</strong> (e.g., <em>Exaggeration</em>). Your annotation will be saved automatically.
    </li>
    <div className="h-3" />
    <li>
      Click <strong>"Next Article"</strong> to complete the brief post-article survey.
    </li>
    <div className="h-3" />
    <li>
      Select <strong>"Submit Survey and Load Next Article"</strong> to move on to the next article.
    </li>
    <div className="h-3" />
  </ul>
  <p></p>
<div className="h-4" />
<p></p>
  <p className="text-sm text-gray-500 italic">
    Make sure your highlights are thoughtful and fall within the required word range—your input helps us better understand how people detect biased or misleading content.
  </p>
</div>

{/* Sticky Selected Text & Word Count */}
{(selectedText || wordCount > 0) && (
  <div className="fixed bottom-4 right-4 bg-white shadow-lg rounded-lg p-4 border border-gray-300 w-64 z-50">
    {selectedText && (
      <p className="text-sm text-gray-700 mb-2 break-words">
        <strong>Selected:</strong> "{selectedText}"
      </p>
    )}
    {wordCount > 0 && (
      <p
        className={`text-xs ${
          wordCount < MIN_WORDS || wordCount > MAX_WORDS
            ? "text-red-600"
            : "text-green-600"
        }`}
      >
        Word Count: {wordCount} (must be {MIN_WORDS}–{MAX_WORDS})
      </p>
    )}
  </div>
)}

        </div>
    );
  }


// Wrapper component that gates the tool behind the intro video
export default function NewsAnnotationTool() {
  const [introDone, setIntroDone] = useState(true);

  // // Uncomment to only require video once per session:
  // useEffect(() => {
  //   const seen = sessionStorage.getItem("introWatched") === "1";
  //   if (seen) setIntroDone(true);
  // }, []);
  // useEffect(() => {
  //   if (introDone) sessionStorage.setItem("introWatched", "1");
  // }, [introDone]);

  if (!introDone) {
    return <IntroScreen onDone={() => setIntroDone(true)} />;
  }
  return <ToolMain />;
}

