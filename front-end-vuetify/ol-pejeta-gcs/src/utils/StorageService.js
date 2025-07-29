// Unified storage service for file and localStorage operations
export class StorageService {
  constructor (localStorageKey = 'ol_pejeta_surveys') {
    this.localStorageKey = localStorageKey
  }

  async saveData (data, filename = null, saveToFile = true, saveToFileFunc = null) {
    const errors = []

    // Try to save to file system first if requested
    if (saveToFile && saveToFileFunc && filename) {
      try {
        await saveToFileFunc(data, filename)
        console.log(`Data saved to file: ${filename}`)
        return { success: true, savedToFile: true }
      } catch (fileError) {
        console.warn('Failed to save to file system, falling back to localStorage:', fileError)
        errors.push({ type: 'file', error: fileError })
      }
    }

    // Fallback to localStorage
    try {
      const existingData = this.loadFromLocalStorage()
      const dataId = data.id || `item_${Date.now()}`
      existingData[dataId] = data
      localStorage.setItem(this.localStorageKey, JSON.stringify(existingData))
      console.log('Data saved to localStorage')
      return { success: true, savedToFile: false, errors }
    } catch (localStorageError) {
      console.error('Failed to save to localStorage:', localStorageError)
      errors.push({ type: 'localStorage', error: localStorageError })
      return { success: false, errors }
    }
  }

  loadFromLocalStorage () {
    try {
      return JSON.parse(localStorage.getItem(this.localStorageKey) || '{}')
    } catch (error) {
      console.error('Error loading from localStorage:', error)
      return {}
    }
  }

  loadAsArray () {
    const data = this.loadFromLocalStorage()
    return Object.values(data)
  }

  async loadFromMultipleSources (loadFromFilesFunc = null) {
    const results = {
      fileData: [],
      localStorageData: [],
      errors: [],
    }

    // Try to load from file system first
    if (loadFromFilesFunc) {
      try {
        const fileSurveys = await loadFromFilesFunc()
        results.fileData = fileSurveys
        console.log(`Loaded ${fileSurveys.length} items from files`)
      } catch (error) {
        console.warn('Error loading from files:', error)
        results.errors.push({ type: 'file', error })
      }
    }

    // Load from localStorage as fallback or supplement
    try {
      results.localStorageData = this.loadAsArray()
      if (results.fileData.length === 0) {
        console.log('No file data found, using localStorage data')
      }
    } catch (error) {
      console.error('Error loading from localStorage:', error)
      results.errors.push({ type: 'localStorage', error })
    }

    return results
  }

  clear () {
    try {
      localStorage.removeItem(this.localStorageKey)
      return { success: true }
    } catch (error) {
      console.error('Error clearing localStorage:', error)
      return { success: false, error }
    }
  }
}
