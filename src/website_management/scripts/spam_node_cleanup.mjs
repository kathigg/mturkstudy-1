// spam_node_cleanup.mjs
import { initializeApp, cert } from "firebase-admin/app";
import { getDatabase } from "firebase-admin/database";
import fs from "fs";

// Load credentials
const serviceAccount = JSON.parse(
  fs.readFileSync("./serviceAccountKey.json", "utf8")
);

// Initialize Admin SDK
initializeApp({
  credential: cert(serviceAccount),
  databaseURL: "https://cisc475database-default-rtdb.firebaseio.com", 
});

const db = getDatabase();
const submissionsRef = db.ref("submissions");

async function cleanupTestingNodes() {
  console.log("Fetching all submissions...");

  const snapshot = await submissionsRef.once("value");
  if (!snapshot.exists()) {
    console.log("No submissions found.");
    return;
  }

  const updates = {};
  let count = 0;

  const nodeToDelete = "TESSTINGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"; // Change this if needed

  snapshot.forEach((childSnap) => {
    const key = childSnap.key;
    const data = childSnap.val();
    const openFeedback = data?.surveyResponses?.[3]?.openFeedback ?? null;

    if (openFeedback === nodeToDelete) {
      updates[key] = null;
      count++;
    }
  });

  if (count === 0) {
    console.log(`No nodes found with openFeedback = "${nodeToDelete}".`);
    return;
  }

  console.log(`Found ${count} spam nodes.`);
  console.log("Deleting now...");

  await submissionsRef.update(updates);

  console.log(`Successfully deleted ${count} spam submission nodes.`);
}

// Run the cleanup
cleanupTestingNodes()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("Error during cleanup:", err);
    process.exit(1);
  });