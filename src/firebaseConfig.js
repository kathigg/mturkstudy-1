import { initializeApp } from "firebase/app";
import { getDatabase, ref, push } from "firebase/database";

const firebaseConfig = {
  apiKey: "AIzaSyCQsWrA1_zCAukNqv3qOUBYXY7KBudFRjQ",
  authDomain: "cisc475database.firebaseapp.com",
  databaseURL: "https://cisc475database-default-rtdb.firebaseio.com",
  projectId: "cisc475database",
  storageBucket: "cisc475database.appspot.com",
  messagingSenderId: "372963635946",
  appId: "1:372963635946:web:7ed6c09fce9f9bff8d1d93",
  measurementId: "G-JZ5HT65P6V",
};

const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

export { database, ref, push };
