import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import AsrDashboard from './pages/AsrDashboard';

function App() {
  return (
    <>
      <Toaster position="top-right"
        toastOptions={{
          style: {
            background: '#333',
            color: '#fff',
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AsrDashboard />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
