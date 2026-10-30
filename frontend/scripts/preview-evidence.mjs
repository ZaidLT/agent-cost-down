// Local preview overlay only. The production report index is never written.
import {createServer} from 'vite'
import react from '@vitejs/plugin-react'
import {readFileSync,existsSync} from 'node:fs'
import {resolve} from 'node:path'
const directory = resolve('../artifacts/frontend-preview')
const files = ['135c81cc2a5991c2.json','04f6d572b16fa8a5.json']
if (files.some(file => !existsSync(resolve(directory,file)))) throw new Error('Copy the exact v4 reports into the ignored artifacts/frontend-preview directory first. See frontend/README.md.')
const server = await createServer({configFile:false,envDir:false,plugins:[react(),{name:'local-evidence-preview',configureServer(server){server.middlewares.use((request,response,next)=>{
 const path=request.url?.split('?')[0]
 if(path==='/reports/index.json'){response.setHeader('Content-Type','application/json');response.end(JSON.stringify({active:files[0],status:'local_preview',reports:[{file:'555720dd79a2c26c.json',label:'v3 original study'},{file:files[0],label:'v4 controlled rerun'},{file:files[1],label:'v4 development'}]}));return}
 const file=files.find(file=>path==='/reports/'+file)
 if(file){response.setHeader('Content-Type','application/json');response.end(readFileSync(resolve(directory,file)));return}
 next()
})}}],server:{host:'127.0.0.1',port:5187,strictPort:true}})
await server.listen();server.printUrls()
