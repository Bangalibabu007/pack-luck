// script.js
document.getElementById('pack-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const packType = document.getElementById('packType').value;
    const contents = document.getElementById('contents').value;
    const openedDate = document.getElementById('openedDate').value;

    const logEntry = document.createElement('li');
    logEntry.textContent = `${openedDate}: ${packType} - ${contents}`;
    document.getElementById('pack-log').appendChild(logEntry);
    
    document.getElementById('pack-form').reset();
});