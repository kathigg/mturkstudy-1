import { doc, setDoc } from "firebase/firestore";
import { db } from "./firebase";

export async function saveAnnotation(articleTitle, workerId, annotations, openFormResponses, completionCode){
    try {
        const safeTitle = articleTitle.replace(/\s+/g,"_");

        await setDoc(doc(db, "annotations", safeTitle, "workers", workerId), {
            workerId, 
            annotations,
            openFormResponses,
            completionCode,
            timestamp: new Date().toISOString(),
        });
    } catch (error) {
        console.error("Error saving annotation:", error);
    }
}