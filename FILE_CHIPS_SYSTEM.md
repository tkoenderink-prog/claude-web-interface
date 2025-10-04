# File Chips Display System

## Overview
The File Chips Display System provides a comprehensive visual interface for managing selected files in the Claude AI web interface. It shows both knowledge files (from the Obsidian vault) and uploaded files as beautiful, interactive chips with real-time token tracking.

## Features

### Visual File Chips
- **Knowledge Files**: Purple gradient chips with 📚 icon
- **Upload Files**: Pink gradient chips with 📎 icon
- **File Information**: Each chip shows filename, token count, and remove button
- **Smooth Animations**: Fade-in/fade-out effects for adding/removing chips

### Token Management
- **Real-time Tracking**: Live updates of total token usage
- **Visual Progress Bar**: Color-coded progress indicator
  - Green (0-60% usage)
  - Yellow (60-80% usage)
  - Red (80%+ usage)
- **Token Limit**: 200,000 token maximum with warnings

### Interactive Features
- **Remove Files**: Click × button to remove files from context
- **Responsive Design**: Adapts to mobile screens
- **Auto-hide**: Container hidden when no files selected
- **Hover Effects**: Subtle animations on chip interaction

## How It Works

### 1. File Selection
- **Knowledge Files**: Select via the Project Knowledge modal (📚 button)
- **Uploaded Files**: Upload via the paperclip button (📎)
- Files automatically appear as chips below the message area

### 2. Token Calculation
- Automatic token estimation for all files
- Real-time updates as files are added/removed
- Visual warnings when approaching limits

### 3. Message Integration
- Selected files automatically included in message context
- Backend receives file references and token counts
- Files persist across messages until manually removed

## Technical Implementation

### Frontend Components
- **FileChipsManager**: Core JavaScript class managing chip display
- **CSS Styling**: Beautiful gradients and animations
- **Integration**: Seamless connection with existing knowledge modal

### Backend Integration
- **API Updates**: Enhanced message endpoints accept file data
- **Token Service**: Calculates token counts for uploaded files
- **File Tracking**: Maintains file associations with conversations

### Key Methods
```javascript
// Add files to chips display
fileChipsManager.addKnowledgeFile(path, name, tokens)
fileChipsManager.addUploadedFile(id, name, tokens)

// Remove files
fileChipsManager.removeFile(id, type)
fileChipsManager.clearAll()

// Get data for API calls
fileChipsManager.getApiData()
```

## Usage Examples

### Adding Knowledge Files
1. Click the 📚 Project Knowledge button
2. Search and select files from your Obsidian vault
3. Click "Add Selected" - files appear as purple chips
4. Send messages with this context automatically included

### Adding Upload Files
1. Click the 📎 paperclip button
2. Select files from your computer
3. Files appear as pink chips with calculated token counts
4. Files are included in subsequent messages

### Removing Files
1. Click the × button on any chip
2. File is removed from context immediately
3. Token counts update automatically
4. Animations provide smooth feedback

## Configuration

### Token Limits
- Default maximum: 200,000 tokens
- Configurable in FileChipsManager constructor
- Visual warnings at 60% and 80% thresholds

### File Types
- Knowledge files: .md, .txt from Obsidian vaults
- Upload files: Based on ALLOWED_EXTENSIONS config
- Token estimation: Automatic for all text-based files

### Responsive Breakpoints
- Desktop: Full-size chips with all features
- Mobile (<768px): Smaller chips, adapted spacing

## Benefits

### User Experience
- **Clear Context Awareness**: See exactly what files are included
- **Easy Management**: Add/remove files with simple clicks
- **Visual Feedback**: Immediate updates and smooth animations
- **Token Transparency**: Understand context usage at all times

### Developer Benefits
- **Clean Integration**: Minimal changes to existing codebase
- **Extensible Design**: Easy to add new file types or features
- **Performance**: Efficient DOM updates with debouncing
- **Maintainable**: Well-structured class-based architecture

## Future Enhancements

### Potential Features
- File preview on chip hover
- Drag-and-drop file reordering
- File type icons for different formats
- Batch file operations
- Context compression suggestions

### Integration Opportunities
- Save file sets as templates
- Share file collections between conversations
- Export file lists for documentation
- Integration with version control

## Troubleshooting

### Common Issues
- **Chips not appearing**: Check console for JavaScript errors
- **Token counts wrong**: Verify token service configuration
- **Animations stuttering**: Check CSS animation performance
- **Files not included**: Verify API endpoint receives file data

### Debug Mode
Enable developer console to see:
- File addition/removal events
- Token calculation details
- API request data
- Animation timing information

## Conclusion

The File Chips Display System transforms file management in the Claude AI interface from invisible to transparent, providing users with clear visual feedback about their context usage while maintaining excellent performance and user experience.