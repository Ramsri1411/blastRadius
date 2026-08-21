import React from 'react';

const Editor = () => {
  return (
    <div className="editor-container">
      <h2>Document Editor</h2>
      <textarea 
        placeholder="Start typing your content here..." 
        rows={10} 
        cols={50}
      />
      <button type="button">Save Document</button>
    </div>
  );
};

export default Editor;