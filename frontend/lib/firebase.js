import { initializeApp } from "firebase/app";
import { getAnalytics, isSupported } from "firebase/analytics";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDjfLcwQXoaqs0tLj6J4wyjkmubYur_syo",
  authDomain: "bsfdvsdvsd.firebaseapp.com",
  projectId: "bsfdvsdvsd",
  storageBucket: "bsfdvsdvsd.firebasestorage.app",
  messagingSenderId: "899658295258",
  appId: "1:899658295258:web:46d0f55ffc6eb7b46ec2e3",
  measurementId: "G-B32KFNEBX8"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Analytics only in the browser and if supported
let analytics;
if (typeof window !== "undefined") {
  isSupported().then((supported) => {
    if (supported) {
      analytics = getAnalytics(app);
    }
  }).catch((err) => {
    console.debug("Firebase Analytics not supported in this environment:", err);
  });
}

export { app, analytics };
