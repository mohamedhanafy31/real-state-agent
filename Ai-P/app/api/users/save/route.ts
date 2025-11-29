import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const DATA_DIR = path.join(process.cwd(), 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');

interface UserInfo {
    name: string;
    phone: string;
    email: string;
    timestamp: string;
}

// Ensure data directory exists
async function ensureDataDir() {
    try {
        await fs.access(DATA_DIR);
    } catch {
        await fs.mkdir(DATA_DIR, { recursive: true });
    }
}

// Read existing users
async function readUsers(): Promise<UserInfo[]> {
    try {
        const data = await fs.readFile(USERS_FILE, 'utf-8');
        return JSON.parse(data);
    } catch {
        // File doesn't exist yet, return empty array
        return [];
    }
}

// Write users to file
async function writeUsers(users: UserInfo[]): Promise<void> {
    await fs.writeFile(USERS_FILE, JSON.stringify(users, null, 2), 'utf-8');
}

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        // Validate required fields
        if (!body.name || !body.phone || !body.email) {
            return NextResponse.json(
                { error: 'Missing required fields' },
                { status: 400 }
            );
        }

        // Validate email format
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(body.email)) {
            return NextResponse.json(
                { error: 'Invalid email format' },
                { status: 400 }
            );
        }

        const newUser: UserInfo = {
            name: body.name.trim(),
            phone: body.phone.trim(),
            email: body.email.trim().toLowerCase(),
            timestamp: body.timestamp || new Date().toISOString(),
        };

        // Ensure data directory exists
        await ensureDataDir();

        // Read existing users
        const users = await readUsers();

        // Check if email already exists
        const existingUser = users.find(u => u.email === newUser.email);
        if (existingUser) {
            return NextResponse.json(
                {
                    message: 'User already exists',
                    user: existingUser
                },
                { status: 200 }
            );
        }

        // Add new user
        users.push(newUser);

        // Write back to file
        await writeUsers(users);

        return NextResponse.json(
            {
                message: 'User saved successfully',
                user: newUser,
                totalUsers: users.length
            },
            { status: 201 }
        );
    } catch (error) {
        console.error('Error saving user:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}

export async function GET() {
    try {
        await ensureDataDir();
        const users = await readUsers();

        return NextResponse.json({
            users,
            total: users.length
        });
    } catch (error) {
        console.error('Error reading users:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
