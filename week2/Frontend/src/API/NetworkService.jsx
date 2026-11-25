import axios from "axios";

const baseUrl = "http://localhost:8000"

const getAllSessions = () => {
    return axios.get(`${baseUrl}\\session`)
}

const createNewSession = () => {
    return axios.post(`${baseUrl}\\session`)
}

const getSession = (sessionId) => {
    return axios.get(`${baseUrl}\\session\\${sessionId}\\chat`)
}

const postToSession = ({sessionId, prompt}) => {
    return fetch(`${baseUrl}\\session\\${sessionId}\\chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({message: prompt})
    })
}

const uploadFile = async (file) => {
    const filename = encodeURIComponent(file.name)

    const response = await fetch(
        `${baseUrl}/uploads?filename=${filename}`,
        {
            method: 'POST',
            headers: {
                'Content-Type': file.type || 'application/octet-stream',
            },
            body: file
        }
    )

    if (!response.ok){
        throw new Error(`Upload failed: ${response.status}`)
    }

    return response.json()
}

const attachFiles = async (sessionId, fileIds) => {
    return axios.post(`${baseUrl}/session/${sessionId}/files`, {
    file_ids: fileIds,
  })
}

export default {
    getAllSessions: getAllSessions,
    createNewSession: createNewSession,
    getSession: getSession,
    postToSession: postToSession,
    uploadFile: uploadFile,
    attachFiles: attachFiles
}