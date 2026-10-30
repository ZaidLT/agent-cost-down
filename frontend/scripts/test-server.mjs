// The test origin is loopback-only and all API responses are intercepted by Playwright.
import {createServer} from 'vite'
import react from '@vitejs/plugin-react'
const server = await createServer({configFile:false,envDir:false,plugins:[react()],define:{'import.meta.env.VITE_API_URL':JSON.stringify('http://127.0.0.1:5499')},server:{host:'127.0.0.1',port:5186,strictPort:true}})
await server.listen()
server.printUrls()
