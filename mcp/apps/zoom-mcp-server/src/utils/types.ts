export interface Meet {
    uuid: string;
    id: number;
    host_id: string;
    topic: string;
    type: number;
    start_time: string;
    duration: number;
    timezone: string;
    created_at: string;
    join_url: string;
    password?: string;
  }
  
  export interface CreateMeetingParams {
    topic: string;
    start_time: string;
    duration?: number;
    timezone?: string;
    agenda?: string;
  }
  
  export interface NewMeeting {
    topic: string;
    start_time: string;
    duration: number;
    timezone: string;
    join_url: string;
    password: string;
    agenda?: string;
  }
  
  export interface UpdateMeetingParams {
    id: string;
    topic?: string;
    start_time?: string;
    duration?: number;
    timezone?: string;
    agenda?: string;
  }
  