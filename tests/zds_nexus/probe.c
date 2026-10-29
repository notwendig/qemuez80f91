#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#define CPPUNIT_NXAPI
#include "nxapi.h"
static int failures;
static void check(const char *name, int ok) { printf("%s: %s\n", ok ? "PASS" : "FAIL",name); fflush(stdout); if(!ok) failures++; }
static void error_callback(const char *s) { printf("DLL: %s\n",s); fflush(stdout); }
int main(int argc,char **argv) {
    nxt_TargetSpec spec; nxt_Status status=99; nxt_Handle *h;
    HMODULE dll;
    if(argc < 3) { fprintf(stderr,"usage: probe.exe DLL ALGO_INI [PORT]\n");return 2; }
    dll=LoadLibraryA(argv[1]);
    nxt_Handle *(*open_fn)(const nxt_TargetSpec*,void(*)(const char*),nxt_Status*);
    nxt_Status (*close_fn)(nxt_Handle*);
    nxt_Status (*control_fn)(nxt_Handle*,nxt_CtrlData);
    if(!dll) { printf("load error %lu\n",GetLastError());return 1; }
    open_fn=(void*)GetProcAddress(dll,"nx_Open");
    close_fn=(void*)GetProcAddress(dll,"nx_Close");
    control_fn=(void*)GetProcAddress(dll,"nx_Control");
    memset(&spec,0,sizeof(spec)); spec.accessPort=NX_PORT_TYPE_OTHER;
    spec.targetEndian=NX_ENDIAN_LITTLE;
    spec.vendorTargetSpec.pOpenParameters=argv[2];
    spec.vendorTargetSpec.comminfo.type=NXV_COMM_TYPE_ETHERNET;
    strcpy(spec.vendorTargetSpec.comminfo.u.ethernet.addr,"127.0.0.1");
    spec.vendorTargetSpec.comminfo.u.ethernet.port=argc>3?atoi(argv[3]):4040;
    printf("open spec=%u ctrl=%u vendor=%u\n",(unsigned)sizeof(spec),(unsigned)sizeof(nxt_CtrlData),(unsigned)offsetof(nxt_CtrlData,vendorDefinedCtrlData));fflush(stdout);
    h=open_fn(&spec,error_callback,&status);
    printf("open handle=%p status=%d\n",h,status);fflush(stdout);
    check("open", h && status==0);
    if(h) {
        nxt_CtrlData c;unsigned long pc=0xabcdef;
        memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_INITIALIZE_TARGET;
        strcpy(c.vendorDefinedCtrlData.u.initializeTarget.cpuName,"eZ80F91");
        c.vendorDefinedCtrlData.u.initializeTarget.systemClockFreq=10000000;
        c.vendorDefinedCtrlData.u.initializeTarget.targetClockFreq=10000000;
        c.vendorDefinedCtrlData.u.initializeTarget.internalROMSize=0x40000;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.adl=1;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.spl=0xfffff0;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.sps=0xffff;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.internalRAM.enable=1;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.internalRAM.page=0xff;
        /* ZDS 5.3.5 adds a size DWORD absent from the SDK 1.1 headers.
         * Its driver explicitly checks size == 0x470 (PE32, pack 4). */
        { unsigned char cfg[0x470] = {0}; unsigned long size=sizeof(cfg); memcpy(cfg,&size,4); memcpy(cfg+4,&c.vendorDefinedCtrlData.u.initializeTarget,sizeof(cfg)-4); memcpy(&c.vendorDefinedCtrlData.u.initializeTarget,cfg,sizeof(cfg)); }
        check("initialize",control_fn(h,c)==0);
        memset(&c,0,sizeof(c));c.cTag=NX_CTRL_RESETORHALT;
        c.u.resetOrHalt.performResetSequence=1;
        c.u.resetOrHalt.haltState=1;
        check("halt",control_fn(h,c)==0);
        memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTER;
        c.vendorDefinedCtrlData.u.getRegister.type=NXV_REGISTER_STANDARD;
        c.vendorDefinedCtrlData.u.getRegister.address=21;
        c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
        status=control_fn(h,c);printf("get pc status=%d pc=%06lx\n",status,pc);fflush(stdout);
        check("initial PC",status==0 && pc==0);
        {
            nxt_SetEvent event;
            nxt_Status (*set_event)(nxt_Handle*,nxt_SetEvent*)=(void*)GetProcAddress(dll,"nx_SetEvent");
            nxt_Status (*write_mem)(nxt_Handle*,int,int,unsigned long,size_t,int,const void*)=(void*)GetProcAddress(dll,"nx_WriteMem");
            nxt_Status (*read_mem)(nxt_Handle*,int,int,unsigned long,size_t,int,void*)=(void*)GetProcAddress(dll,"nx_ReadMem");
            unsigned char pattern[]={0,0x3e,0x42,0x18,0xfb},readback[5]={0};
            void *destination=readback;
            memset(&c,0,sizeof(c)); c.cTag=NXV_CTRL_SET_REGISTER;
            c.vendorDefinedCtrlData.u.setRegister.address=2;
            c.vendorDefinedCtrlData.u.setRegister.value=0x123456;
            check("set BC",control_fn(h,c)==0);
            c.cTag=NXV_CTRL_GET_REGISTER;c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
            status=control_fn(h,c);check("read BC",status==0 && pc==0x123456);
            {
                nxvt_Registers all;
                memset(&all,0,sizeof(all));memset(&c,0,sizeof(c));
                c.cTag=NXV_CTRL_GET_REGISTERS_ALL;c.vendorDefinedCtrlData.u.getRegistersAll.pBuf=&all;
                check("register view: full snapshot",control_fn(h,c)==0);
                check("register view: PC",all.pc==0);
                memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTER;
                c.vendorDefinedCtrlData.u.getRegister.address=2;c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
                status=control_fn(h,c);check("register view preserves BC",status==0 && pc==0x123456);
            }

            check("write RAM",write_mem(h,1,0,0xffe000,sizeof(pattern),0,pattern)==0);
            check("read RAM",read_mem(h,1,0,0xffe000,sizeof(readback),0,&destination)==0);
            check("RAM contents",memcmp(readback,pattern,sizeof(pattern))==0);
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_SET_REGISTER;
            c.vendorDefinedCtrlData.u.setRegister.address=21;
            c.vendorDefinedCtrlData.u.setRegister.value=0xffe000;
            check("set PC",control_fn(h,c)==0);
            memset(&event,0,sizeof(event));event.eType=NX_ETYPE_STEP;
            check("single step",set_event(h,&event)==0);
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTER;
            c.vendorDefinedCtrlData.u.getRegister.address=21;
            c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
            status=control_fn(h,c);printf("stepped PC=%06lx\n",pc);check("step PC",status==0 && pc==0xffe001);
            {
                nxvt_Registers snapshot;
                memset(&snapshot,0,sizeof(snapshot));memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTERS_ALL;
                c.vendorDefinedCtrlData.u.getRegistersAll.pBuf=&snapshot;
                status=control_fn(h,c);printf("register snapshot PC=%06lx\n",snapshot.pc);
                check("register view: nonzero PC",status==0 && snapshot.pc==0xffe001);
            }

            {
                nxt_ReceivedEvent received;
                nxt_Status (*get_event)(nxt_Handle*,nxt_ReceivedEvent*,int,int)=(void*)GetProcAddress(dll,"nx_GetEvent");
                memset(&received,0,sizeof(received));
                do { status=get_event(h,&received,sizeof(received),1); } while(status==0 && received.rTag!=NX_READ_EVENT_BREAKSTEP);
                check("step event",status==0 && received.rTag==NX_READ_EVENT_BREAKSTEP);
                memset(&event,0,sizeof(event));event.eType=NX_ETYPE_BREAKPOINT;
                event.eid=h->cap.breakMinEventId;event.u.breakpoint.op=NX_BREAKPOINT_INSTRADDR;
                event.u.breakpoint.addr=0xffe003;
                printf("breakpoint id %d\n",event.eid);
                check("set breakpoint",set_event(h,&event)==0);
                memset(&c,0,sizeof(c));c.cTag=NX_CTRL_RESETORHALT;
                check("run",control_fn(h,c)==0);
                memset(&received,0,sizeof(received));
                do { status=get_event(h,&received,sizeof(received),1); printf("event status=%d tag=%x\n",status,received.rTag); fflush(stdout); } while(status==0 && received.rTag!=NX_READ_EVENT_BREAKSTEP);
                check("breakpoint event",status==0 && received.rTag==NX_READ_EVENT_BREAKSTEP);
                memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTER;
                c.vendorDefinedCtrlData.u.getRegister.address=21;
                c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
                status=control_fn(h,c);printf("break PC=%06lx\n",pc);
                check("breakpoint PC",status==0 && pc==0xffe003);
                c.vendorDefinedCtrlData.u.getRegister.address=0;
                status=control_fn(h,c);check("executed LD A",status==0 && pc==0x42);
                {
                    void (*clear_event)(nxt_Handle*,int)=(void*)GetProcAddress(dll,"nx_ClearEvent");
                    nxvt_TargetStatus target_status=NXV_TARGET_STATUS_UNKNOWN;
                    clear_event(h,event.eid);
                    memset(&c,0,sizeof(c));c.cTag=NX_CTRL_RESETORHALT;
                    check("resume without breakpoint",control_fn(h,c)==0);
                    Sleep(50);
                    c.cTag=NXV_CTRL_GET_TARGET_STATUS;
                    c.vendorDefinedCtrlData.u.getTargetStatus.pStatus=&target_status;
                    status=control_fn(h,c);
                    check("running status",status==0 && target_status==NXV_TARGET_STATUS_RUNNING);
                    memset(&c,0,sizeof(c));c.cTag=NX_CTRL_RESETORHALT;c.u.resetOrHalt.haltState=1;
                    check("stop running CPU",control_fn(h,c)==0);
                }

            }

        }
        close_fn(h);
    }
    return failures?1:0;
}
