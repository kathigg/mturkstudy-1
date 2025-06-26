import React, { useState, useEffect } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CardContent } from "../components/CardContent";
import Papa from "papaparse";

import { database, ref, push } from "../firebaseConfig";

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

const DropdownItem = ({ icon, title, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  return (
      <div className="mb-1">
          <button
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center justify-between w-full text-left text-sm font-bold text-gray-800 hover:text-blue-600 focus:outline-none"
          >
              <span>{icon} {title}</span>
              <span>{isOpen ? "−" : "+"}</span>
          </button>
          {isOpen && (
              <div className="mt-1 ml-4 text-xs text-gray-700 transition-all duration-200">
                  {children}
              </div>
          )}
      </div>
  );
};


export default function NewsAnnotationTool() {
    const [articles, setArticles] = useState([]);
    const [currentArticleIndex, setCurrentArticleIndex] = useState(0);
    const [annotations, setAnnotations] = useState({});
    const [selectedText, setSelectedText] = useState("");
    const [textAnnotations, setTextAnnotations] = useState({});
    const [selectedCategory, setSelectedCategory] = useState("");
    const [selectedSubcategory, setSelectedSubcategory] = useState("");
    const [showRightInstructions, setShowRightInstructions] = useState(true);
    const handleCategoryButtonClick = (categoryKey) => {
      setSelectedCategory(categoryKey);
      setSelectedSubcategory(""); // Clear the subcategory so user chooses it fresh
    };

    const categoryOptions = {
      Persuasive_Propaganda: ["Repetition", "Exaggeration", "Flag-Waving", "Slogans", "Bandwagon", "Causal Oversimplification", "Doubt"],
      Inflammatory_Language: ["Demonization", "Name-Calling", "Hyperbole", "Straw Man Arguments"],
  };

    const [showSurvey, setShowSurvey] = useState(false);
    const [surveyResponses, setSurveyResponses] = useState({});
    const [confidence, setConfidence] = useState(0);
    const [bias, setBias] = useState(0);
    const [openFeedback, setOpenFeedback] = useState("");
    const [showThankYou, setShowThankYou] = useState(false);

    const articleId = articles[currentArticleIndex]?.id;
  
    const countWords = (text) => {
      return text.trim().split(/\s+/).filter(Boolean).length;
    };

const autoSaveAnnotation = (category, subcategory) => {
  if (selectedText && category && subcategory && articleId) {
    setTextAnnotations((prevAnnotations) => ({
      ...prevAnnotations,
      [articleId]: [
        ...(prevAnnotations[articleId] || []),
        { text: selectedText, category, subcategory },
      ],
    }));
    
    setSelectedText("");
    setSelectedCategory("");
    setSelectedSubcategory("");
    
  }
};

// Update category and subcategory selection handlers
const handleCategoryChange = (e) => {
  const newCategory = e.target.value;
  setSelectedCategory(newCategory);
  if (selectedText && selectedSubcategory) {
    autoSaveAnnotation(newCategory, selectedSubcategory);
  }
};

const handleSubcategoryChange = (e) => {
  const newSubcategory = e.target.value;
  setSelectedSubcategory(newSubcategory);
  if (selectedText && selectedCategory) {
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
      
    

    // useEffect(() => {
    //     setArticles(shuffleArray([...sampleArticles]));
    // }, []);

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
    /*
        setArticles(shuffleArray([...sampleArticles.slice(0, 3)]));
      }, []);
    */

    const handleNextArticle = () => {
        if (showSurvey) {
            //validate survey responses here
            if (
              confidence === 0 ||
              bias === 0 ||
              openFeedback.trim() === ""
            ) {
              alert("Please answer all survey questions before continuing.");
              return;
            }

                // Validate that there is at least one valid annotation

            const articleId = articles[currentArticleIndex]?.id;
            const annotationsForArticle = textAnnotations[articleId] || [];

            if (annotationsForArticle.length === 0) {
                alert("Please annotate at least one phrase before continuing.");
                return;
              }
          
              const anyInvalid = annotationsForArticle.some(
                (a) => !a.category || !a.subcategory
              );
          
              if (anyInvalid) {
                alert("Each annotation must include a category and subcategory.");
                return;
              }
    // Save survey responses and continue

            setSurveyResponses((prev) => ({
              ...prev,
              [articleId]: { confidence, bias, openFeedback },
            }));
      
            if (currentArticleIndex < articles.length - 1) {
              setCurrentArticleIndex(currentArticleIndex + 1);
              setSelectedText("");
              setSelectedCategory("");
              setSelectedSubcategory("");
              setShowSurvey(false);
              setConfidence(0);
              setBias(0);
              setOpenFeedback("");
            } else {
              setShowThankYou(true);
            }
          } else {
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
        if (selectedText && selectedCategory && selectedSubcategory) {
            const articleId = articles[currentArticleIndex]?.id;
            setTextAnnotations((prevAnnotations) => ({
                ...prevAnnotations,
                [articleId]: [
                    ...(prevAnnotations[articleId] || []),
                    { text: selectedText, category: selectedCategory, subcategory: selectedSubcategory },
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
        const completionCode = generateCode();

    useEffect(() => {
        if (showThankYou) {
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


    if (showThankYou) {


        return (
          <div className="w-full h-screen flex items-center justify-center bg-white">
            <div className="max-w-xl text-center p-6 border border-gray-300 rounded shadow">
              <h2 className="text-2xl font-bold mb-4">🎉 Thank You!</h2>
              <p className="mb-4 text-gray-700">Thank you for taking part in this study. Your responses have been recorded.</p>
              <p className="mb-4 text-gray-700">Please copy and paste the following completion code into MTurk:</p>
              <div className="bg-gray-100 text-lg font-mono p-4 rounded border border-dashed border-gray-400 mb-4">{completionCode}</div>
              <p className="text-sm text-gray-500">You may now close this window or return to the task page.</p>
              {process.env.NODE_ENV !== "production" && (
            <Button onClick={() => downloadAnnotations(annotations, textAnnotations, surveyResponses)} className="mt-4 bg-purple-600 text-white">
              Download All Responses (JSON)
            </Button>
          )
  }          
            </div>
          </div>
        );
      }

    return (
        <div className="flex w-full justify-center items-start min-h-screen bg-gray-100">
            {/* Instructions Sidebar */}
            <div className={`w-1/4 p-4 bg-gray-200 shadow-md transition-all duration-300 ${showRightInstructions ? "visible opacity-100 pointer-events-auto" : "invisible opacity-0 pointer-events-none"}`}>
                <h3 className="text-lg font-bold mb-2">Annotation Guide</h3>
                <p className="text-sm mb-2">Use the following categories for labeling:</p>
                <div className="bg-yellow-100 p-2 rounded mb-2">
                    <div></div>
                  <div className="bg-yellow-100 p-3 rounded mb-3">
                    <strong className="text-yellow-600 text-center block mb-2 text-base">Persuasive Propaganda</strong>
                    <DropdownItem icon=" " title="Repetition">Reinforcing a message by repeating it.</DropdownItem>
                    <DropdownItem icon=" " title="Exaggeration">Overstating or distorting facts.</DropdownItem>
                    <DropdownItem icon=" " title="Flag-Waving">Linking a message to patriotism or national pride.</DropdownItem>
                    <DropdownItem icon=" " title="Slogans">Catchy, emotional phrases designed to influence opinions.</DropdownItem>
                    <DropdownItem icon=" " title="Bandwagon">Encouraging action by claiming "everyone is doing it."</DropdownItem>
                    <DropdownItem icon=" " title="Casual Oversimplification">Reducing a complex issue to a single cause or solution.</DropdownItem>
                    <DropdownItem icon=" " title="Doubt">Sowing uncertainty or questioning the credibility of evidence.</DropdownItem>
                </div>

                </div>
                <div className="bg-red-100 p-2 rounded mb-6">
                    <strong className="text-red-600 text-center block mb-3 mt-3">Inflammatory Language</strong>
                    <ul className="text-s text-center ml-2">
                    <DropdownItem icon=" " title="Name-Calling">Using demeaning labels or insults to discredit opponents.</DropdownItem>
                    <DropdownItem icon=" " title="Hyperbole">Exaggerating to provoke fear, anger, or excitement.</DropdownItem>
                    <DropdownItem icon=" " title="Demonization">Portraying individuals or groups as evil, immoral, or dangerous.</DropdownItem>
                    <DropdownItem icon=" " title="Straw-Man">Misrepresenting someone's argument to make it easier to attack.</DropdownItem>
                    </ul>
                </div>
            
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
                        Flame Rhetoric
                    </Button>
                    <Button onClick={() => handleCategoryButtonClick("Persuasive_Propaganda")} className="bg-yellow-500">
                        Persuasive Propaganda
                    </Button>
                </div>


{selectedText && (
  <div className="mt-4 flex flex-col items-center">
    <p className="text-sm text-gray-700 mb-2">Selected Text: "{selectedText}"</p>
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

            <label className="block mt-4">1. How confident are you in your tagging decisions?</label>
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
      {val} – {["Not at all confident", "Slightly confident", "Moderately confident", "Very confident", "Extremely confident"][val - 1]}
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
  3. Why did you tag this way? What made it stand out?
</label>
<p className="text-sm text-gray-600 mb-1">
  Word count: {countWords(openFeedback)} (minimum 5 words)
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
    countWords(openFeedback) < 5
  }
>
  {currentArticleIndex < articles.length - 1
    ? "Submit Survey & Load Next Article"
    : "Finish"}
</Button>
          </div>
        ) : (
          <div className="mt-6">
            <Button onClick={handleNextArticle} className="bg-blue-500">Next Article</Button>
          </div>
        )}
            </div>


{/* Instructions Panel on Right */}
<div className={`w-1/4 p-4 bg-white transition-all duration-300 ${showRightInstructions ? "visible opacity-100 pointer-events-auto" : "invisible opacity-0 pointer-events-none"}`}>
    <h3 className="text-lg font-bold mb-3">📝 Instructions</h3>
    <p className="text-sm">
    You will annotate <strong>3 news articles</strong>. For each article, please follow these steps:
  </p>
  <div className="h-4" />
  <div className="h-4" />
  <ul className="list-decimal list-inside text-sm space-y-1">
    <li>
      <strong>Highlight a section of text</strong> between [] and [] words that you want to annotate.
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
        </div>
    );
  }