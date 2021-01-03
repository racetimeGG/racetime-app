import React from "react";
import Navigation from "../components/navigation";

import "tailwindcss/tailwind.css";
import "../styles/globals.scss";
import "../styles/ui.scss";
import Footer from "../components/footer";
import AuthProvider from "../components/user/auth-provider";

export default function MyApp({Component, pageProps}) {
    return (
        <AuthProvider>
            <div id="application">
                <nav>
                    <Navigation/>
                </nav>
                <main>
                    <Component {...pageProps} />
                </main>
                <footer>
                    <Footer/>
                </footer>
            </div>
        </AuthProvider>
    );
}

