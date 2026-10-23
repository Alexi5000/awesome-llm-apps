import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getSessionUserId, unauthorizedResponse } from '@/lib/session';

export async function GET() {
  try {
    const userId = await getSessionUserId();
    if (!userId) {
      return unauthorizedResponse();
    }

    const tripPlans = await prisma.tripPlan.findMany({
      where: { userId },
      orderBy: {
        createdAt: 'desc'
      }
    });

    return NextResponse.json(
      {
        success: true,
        tripPlans
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error fetching trip plans:', error);
    return NextResponse.json(
      {
        success: false,
        message: 'Failed to fetch trip plans'
      },
      { status: 500 }
    );
  }
}