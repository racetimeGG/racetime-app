## Getting Started

Before you begin, make sure that you have [Node.js and NPM](https://nodejs.org/en/) installed. Also make sure you got 
[racetime-app](https://github.com/spell/racetime-app) running and working, using the `api-experimental` branch.

1. Navigate to `localhost:8000/admin` and create a new confidential OpenID Client using the `id_token`
   authorization flow. Make sure it has access to at least the `openid`  claim and register the
   `http://localhost:3000` callback URL.
2. Copy the file called `.env.local.example` in the root of the project to `.env.local`, and change the value to point
   to your instance of [`racetime.dev`](https://github.com/racetimeGG/racetime-app).
3. Change `NEXT_PUBLIC_AUTH_CLIENT_ID` to the client ID of the created client in step 2.
4. Install dependencies by running `npm install`.
5. Run the development server.

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser and have a look around.

## Contributing

Contributors are welcome, please refer to the [issues page](https://github.com/spell/racetime-client/issues) or join us
at our [Discord](https://discord.racetime.gg) to see what you can do, or just start hacking away!
