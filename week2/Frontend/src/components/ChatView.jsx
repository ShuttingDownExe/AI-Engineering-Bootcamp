import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

import { useState } from 'react'


export function PromptWindow({
    prompt,
    onPromptChange,
    onClickSendPrompt,
    disabled
}) {
    const handleSubmit = (event) => {
        event.preventDefault()
        if (disabled || !prompt.trim()) return
        onClickSendPrompt()
    }
    return (
        <form onSubmit={handleSubmit}>
            <input 
            value={prompt}
            onChange={event => onPromptChange(event.target.value)}
            placeholder="Enter your prompt here"
            disabled={disabled}
            />
            <button 
            type='submit'
            disabled={disabled || !prompt.trim()}
            >
                Send
            </button>
        </form>
    )
}

export function AssistantMessage({content, reasoning}) {
    return (
        <div>
            {
                reasoning && (
                    <details className='message-bubble assistant'>
                        <summary>
                            Reasoning
                        </summary>
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {reasoning}
                        </ReactMarkdown>
                    </details>
                )
            }
            {
                content && (
                    <div className='message-bubble assistant'>
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                            {content}
                        </ReactMarkdown>
                    </div>
                )
            }
        </div>
    )
}

export function MessagesWindow({messages, answer, reasoning}) {
    return (
        <div className='message-list'>
            {
                messages.filter(
                    message => message.persona === 'user' || message.persona === 'assistant'
                ).map(
                    message => message.persona === 'assistant' ? (
                        <AssistantMessage key={message.id} content={message.content} reasoning={message.reasoning}/>
                    ) : (
                        <div key={message.id} className='message-bubble user'>
                            {message.content}
                        </div>
                    )
                )
            }
            {(answer || reasoning) && (
                <AssistantMessage content={answer} reasoning={reasoning}/>
            )}
        </div>
    )
}

export function PromptDropZone({onFilesDropped, children}){
    const [isDragging, setIsDragging] = useState(false)

    const containsFiles = event => Array.from(event.dataTransfer.types).includes('Files')

    return (
        <div
        className={`prompt-drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragEnter={
            event => {
                if (!containsFiles(event)) return
                event.preventDefault()
                setIsDragging(true)
            }
        }
        onDragOver={
            event => {
                if (!containsFiles(event)) return
                event.preventDefault()
                event.dataTransfer.dropEffect = 'copy'
            }
        }
        onDragLeave={
            event => {
                if (!event.currentTarget.contains(event.relatedTarget)) {
                    setIsDragging(false)
                }
            }
        }
        onDrop={
            event => {
                event.preventDefault()
                setIsDragging(false)
                const files = Array.from(event.dataTransfer.files)
                if (files.length) onFilesDropped(files)
            }
        }
        >
            {isDragging && (
                <div className='drop-overlay'> Drop Files to Upload</div>
            )}
            {children}
        </div>
    )
}