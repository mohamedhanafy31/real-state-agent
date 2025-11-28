import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    const tunnelsFile = path.join(process.cwd(), '.ngrok-tunnels.json');
    
    if (!fs.existsSync(tunnelsFile)) {
      return NextResponse.json(
        { error: 'Ngrok tunnels file not found. Run the ngrok script first.' },
        { status: 404 }
      );
    }

    const tunnelsData = fs.readFileSync(tunnelsFile, 'utf-8');
    const tunnels = JSON.parse(tunnelsData);

    return NextResponse.json(tunnels);
  } catch (error) {
    console.error('Error reading ngrok tunnels:', error);
    return NextResponse.json(
      { error: 'Failed to read ngrok tunnels' },
      { status: 500 }
    );
  }
}

