import {Routes, Route, useParams} from 'react-router'
import ChatPage from './pages/ChatPage'

function ChatRoute() {
  const {sessionId} = useParams()

  return(
    <ChatPage
      key={sessionId ?? 'New Chat'}
      sessionId={sessionId}
    />
  )
}

export default function App() {
  return(
    <Routes>
      <Route path='/' element={<ChatRoute/>}/>
      <Route path='/chat/:sessionId' element={<ChatRoute/>}/>
      <Route path='*' element={<p>Page Not Found</p>}/>
    </Routes>
  )
}