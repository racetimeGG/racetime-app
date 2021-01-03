export const constructAuthorizationURI = (host: string, clientId: string, redirectUri: string, scopes: string[]) => {
    const url = new URL("/openid/authorize", host);
    url.searchParams.append("response_type", encodeURI("id_token"));
    url.searchParams.append("client_id", encodeURI(clientId));
    url.searchParams.append("redirect_uri" , encodeURI(redirectUri));
    url.searchParams.append("scope", encodeURI(scopes.join(" ")));
    url.searchParams.append("nonce", encodeURI("testtest"));
    console.log(url.href);
    return url.href;
}

