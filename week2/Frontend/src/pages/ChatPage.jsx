import { useState, useEffect, useRef } from 'react';

import {SessionList, SessionCreate} from '../components/SessionBar'
import {PromptWindow, MessagesWindow, PromptDropZone} from '../components/ChatView'
import NetworkService from '../API/NetworkService';

import { useNavigate } from 'react-router';

const ChatPage = ({sessionId}) => {
  const [sessionsList, setSessionsList] = useState([])
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState([])
  const [answer, setAnswer] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [reasoning, setReasoning] = useState('')
  const [uploads, setUploads] = useState([])

  const navigate = useNavigate()

  useEffect(() => {
    NetworkService.getAllSessions().then(response => {
        setSessionsList(response.data)
      }).catch(error => {
        setError(error.message)
      })
  },[])

  useEffect(() => {
    if (sessionId) {
      NetworkService.getSession(sessionId).then(response => {
        setMessages(response.data)
      }).catch(error => {
        setError(error.message)
      })
    }
  },[sessionId])

  const chatWindowRef = useRef(null)

  useEffect(() => {
    const container = chatWindowRef.current
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, answer, reasoning])

  const draftSessionId = useRef(null)
  const startNewChat = async () => {
    if (isLoading) return
    draftSessionId.current = null
    setMessages([])
    setPrompt('')
    setAnswer('')
    setReasoning('')
    setError('')

    navigate('/')
  }

  const selectSession = (id) => {
    if (isLoading) return

    if (isLoading || id === sessionId) return
    navigate(`/chat/${id}`)
  }

  const sendPrompt = async () => {
    if (!prompt.trim() || isLoading) return

    if (uploads.some(upload => upload.status === 'uploading')){
      setError('Wait for uploads to finish before sending')
      return
    }

    if (uploads.some(upload => upload.status === 'failed')){
      setError('Remove or retry failed uploads before sending')
      return
    }

    const fileIds = uploads
    .filter(upload => upload.status === 'uploaded')
    .map(upload => upload.fileId)

    setReasoning('')

    const submittedPrompt = prompt.trim()

    setIsLoading(true)
    setError('')
    setAnswer('')
    setPrompt('')

    setMessages(previous => [
      ...previous,
      {
        id: crypto.randomUUID(),
        persona: 'user',
        content: submittedPrompt,
      }
    ])

    try {

        let activeSessionId = sessionId ?? draftSessionId.current

        if (!activeSessionId) {
            const {data} = await NetworkService.createNewSession()
            activeSessionId = data.id
            draftSessionId.current = data.id

            setSessionsList(previous => [
                ...previous,
                {id: data.id, name: data.name}
            ])
        }

        if (fileIds.length > 0){
          await NetworkService.attachFiles(activeSessionId, fileIds)
          setUploads(previous => previous.filter(upload => !fileIds.includes(upload.fileId)))
        }

      const response = await NetworkService.postToSession({
        sessionId:  activeSessionId,
        prompt: submittedPrompt
      })

      if(!response.ok){
        throw new Error(`Request failed: ${response.status}`)
      }

      if (!response.body) {
        throw new Error(`No Stream Found`)
      }

      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader()

      let buffer = ''

      try {
        while(true) {
          const {value, done} = await reader.read()

          if (done) break

          buffer += value

          let boundary
          while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const event = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary+2)

            if (!event.startsWith('data: ')) continue

            const payload = JSON.parse(event.slice(6))

            if (payload.type === 'reasoning') {
              setReasoning(previous => previous + payload.text)
            } else if(payload.type === 'answer'){
              setAnswer(previous => previous + payload.text)
            } else if (payload.type === 'title'){
                setSessionsList(previous => 
                    previous.map(
                        session => session.id === activeSessionId ? {...session, name: payload.text} : session
                    )
                )
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

      const savedMessages = await NetworkService.getSession(activeSessionId)
      setMessages(savedMessages.data)
      setAnswer('')
      setReasoning('')

      const sessions = await NetworkService.getAllSessions()
      setSessionsList(sessions.data)
      if (!sessionId) {
        navigate(`/chat/${activeSessionId}`, {replace: true})
      }
    } catch (error) {
      setError(error.message)
    } finally {
      setIsLoading(false)
    }
  }

  const uploadFiles = async (files) => {
    const entries = files.map(file => ({
      localId: crypto.randomUUID(),
      name: file.name,
      status: 'uploading',
      file,
    }))

    setUploads(previous => [
      ...previous,
      ...entries.map((({ localId, name, status}) => ({
        localId,
        name,
        status
      })))
    ])

    await Promise.allSettled(
      entries.map(async ({localId, file}) => {
        try {
          const uploaded = await NetworkService.uploadFile(file)

          setUploads(previous => 
          previous.map(item => 
            item.localId === localId 
            ? {...item, status: 'uploaded', fileId: uploaded.id} : item
            )
          )
        } catch (error) {
          setUploads(previous => 
            previous.map(item => 
              item.localId === localId ? {
                ...item,
                status: 'failed',
                error: error.message
              } : item
            ) 
          )
        }
      })
    )
  }

  
  return (
    <>
    <div className='chat-layout'>

      <aside id='sessions_bar'>
        <SessionCreate onSelectSession={startNewChat}/>
        <SessionList 
          sessions={sessionsList}
          selectedSessionID={sessionId}
          onSelectSession={selectSession}
        />
      </aside>

      <main className='chat-content'>
        <div className='chat-messages' ref={chatWindowRef}>
          <MessagesWindow messages={messages} answer={answer} reasoning={reasoning}/>
          {error && <p role='alert'>{error}</p>}
        </div>

        {
          uploads.map(upload => (
            <div key={upload.localId}>
              {upload.name}: {upload.status}
              {upload.error && `- ${upload.error}`}
            </div>
          ))

        }

        <div className='chat-composer'>
          <PromptDropZone onFilesDropped={uploadFiles}>
            <PromptWindow 
              prompt={prompt}
              onPromptChange={setPrompt}
              onClickSendPrompt={sendPrompt}
              disabled={isLoading}
          />
          </PromptDropZone>
          
        </div>
      </main>
    </div>
    </>
  )
}

export default ChatPage
