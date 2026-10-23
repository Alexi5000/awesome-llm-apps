import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getSessionUserId, unauthorizedResponse } from '@/lib/session';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const userId = await getSessionUserId();
    if (!userId) {
      return unauthorizedResponse();
    }

    const { id } = await params;

    // Only the owner can read a plan; other callers get the same 404 as a missing plan
    const tripPlan = await prisma.tripPlan.findFirst({
      where: { id, userId },
      include: {
        status: true,
        output: true,
      },
    });

    if (!tripPlan) {
      return NextResponse.json(
        {
          success: false,
          message: 'Trip plan not found'
        },
        { status: 404 }
      );
    }

    return NextResponse.json(
      {
        success: true,
        tripPlan
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error fetching trip plan:', error);
    return NextResponse.json(
      {
        success: false,
        message: 'Failed to fetch trip plan'
      },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const userId = await getSessionUserId();
    if (!userId) {
      return unauthorizedResponse();
    }

    const { id } = await params;

    // First check if the plan exists and belongs to the caller
    const tripPlan = await prisma.tripPlan.findFirst({
      where: { id, userId },
    });

    if (!tripPlan) {
      return NextResponse.json(
        {
          success: false,
          message: 'Trip plan not found'
        },
        { status: 404 }
      );
    }

    // Delete related records first (status and output)
    await prisma.tripPlanStatus.deleteMany({
      where: { tripPlanId: id },
    });

    await prisma.tripPlanOutput.deleteMany({
      where: { tripPlanId: id },
    });

    // Delete the trip plan
    await prisma.tripPlan.delete({
      where: { id },
    });

    return NextResponse.json(
      {
        success: true,
        message: 'Trip plan deleted successfully'
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error deleting trip plan:', error);
    return NextResponse.json(
      {
        success: false,
        message: 'Failed to delete trip plan'
      },
      { status: 500 }
    );
  }
}