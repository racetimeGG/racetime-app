import React from "react";
import {UserManager} from "oidc-client";

const AuthContext = React.createContext(undefined);

export default function AuthProvider(props: React.PropsWithChildren<{}>) {
    const [loading, setLoading] = React.useState<boolean>(true);
    const [isAuthenticated, setIsAuthenticated] = React.useState<boolean>(false);
    const [userManager, setUserManager] = React.useState<UserManager | undefined>(undefined);

    React.useEffect(() => {
        setUserManager(new UserManager({
            authority: process.env.NEXT_PUBLIC_AUTH_AUTHORITY as string,
            client_id: process.env.NEXT_PUBLIC_AUTH_CLIENT_ID as  string,
            redirect_uri: process.env.NEXT_PUBLIC_AUTH_REDIRECT_URI as string,
            scope: "openid",
        }));
    }, []);

    React.useEffect(() => {
        if (userManager) {
            userManager.events.addUserLoaded(user => {
                setIsAuthenticated(true);
                console.log(user.profile.sub);
            });
            userManager.events.addUserUnloaded(() => {
                setIsAuthenticated(false);
                console.log("User logged out...");
            });

            setLoading(false);
        }
    }, [userManager]);

    return (
        <AuthContext.Provider value={{}}>
            {props.children}
        </AuthContext.Provider>
    )
}

export const useAuth = () => React.useContext(AuthContext);
