/* Open ZDS II debug panes without toggling panes that are already visible.
 * IDs are discovered from the installed IDE's accelerator resources. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static HWND ide;
static UINT commands[10];
static const char *panes[10]={
    "Registers","Special Function Registers","Clock","Memory","Watch",
    "Locals","Call Stack","Symbols","Disassembly","Simulated UART Output"
};
static const char *wanted;
static int visible;
static HWND pane;

static BOOL CALLBACK find_ide(HWND window,LPARAM unused)
{
    char title[512];
    (void)unused;
    GetWindowTextA(window,title,sizeof(title));
    if(IsWindowVisible(window) && strstr(title,"camel24 -- ZDSII")) {
        ide=window; return FALSE;
    }
    return TRUE;
}
static BOOL CALLBACK find_pane(HWND window,LPARAM unused)
{
    char title[256];
    (void)unused;
    GetWindowTextA(window,title,sizeof(title));
    if(!strcmp(title,wanted) && IsWindowVisible(window)) { visible=1; pane=window; }
    return TRUE;
}
static int pane_visible(const char *name)
{
    wanted=name; visible=0; pane=NULL; EnumChildWindows(ide,find_pane,0); return visible;
}
static BOOL CALLBACK accelerators(HMODULE module,LPCSTR type,LPSTR name,LONG_PTR unused)
{
    HRSRC resource=FindResourceA(module,name,type);
    const WORD *data=(const WORD*)LockResource(LoadResource(module,resource));
    DWORD size=SizeofResource(module,resource),i;
    (void)unused;
    if(!data) return TRUE;
    for(i=0;i+8<=size;i+=8) {
        const WORD *entry=data+i/2;
        if((entry[0]&0x10) && entry[1]>='0' && entry[1]<='9')
            commands[entry[1]-'0']=entry[2];
    }
    return TRUE;
}
static BOOL CALLBACK memory_space(HWND window,LPARAM apply)
{
    char kind[80]; WCHAR text[256]; int count,i;
    GetClassNameA(window,kind,sizeof(kind));
    if(strcmp(kind,"ComboBox")) return TRUE;
    count=(int)SendMessageA(window,CB_GETCOUNT,0,0);
    for(i=0;i<count;i++) {
        SendMessageW(window,CB_GETLBTEXT,i,(LPARAM)text);
        printf("Memory choice %d: %ls\n",i,text);
        if(apply && (!wcscmp(text,L"Memory") || !wcscmp(text,L"ROM"))) {
            SendMessageA(window,CB_SETCURSEL,i,0);
            PostMessageA(GetParent(window),WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(window),CBN_SELCHANGE),(LPARAM)window);
        }
    }
    return TRUE;
}
int main(int argc,char **argv)
{
    HMODULE exe; int i,failures=0,open;
    if(argc!=3 || (strcmp(argv[1],"--open") && strcmp(argv[1],"--list"))) {
        fprintf(stderr,"usage: views.exe --open|--list Zds2Ide.exe\n");return 2;
    }
    open=!strcmp(argv[1],"--open");
    EnumWindows(find_ide,0);
    if(!ide) { fprintf(stderr,"CAMEL24 ZDS II window not found\n");return 1; }
    exe=LoadLibraryExA(argv[2],NULL,LOAD_LIBRARY_AS_DATAFILE);
    if(!exe) { fprintf(stderr,"Cannot read IDE resources: %lu\n",GetLastError());return 1; }
    EnumResourceNamesA(exe,RT_ACCELERATOR,accelerators,0);
    for(i=0;i<10;i++) {
        int shown=pane_visible(panes[i]),wait;
        if(open && !shown && commands[i]) {
            PostMessageA(ide,WM_COMMAND,commands[i],0);
            for(wait=0;wait<100 && !pane_visible(panes[i]);wait++) Sleep(100);
            shown=pane_visible(panes[i]);
        }
        printf("%s: %s (command %u)\n",panes[i],shown?"visible":"hidden",commands[i]);
        fflush(stdout);
        if(open && !shown) failures++;
    }
    /* ZDS may retain the pre-download register cache when this pane was
     * already docked. Reopen it once after the target has stopped at _main. */
    if(open && pane_visible("Registers") && commands[0]) {
        int wait;
        PostMessageA(ide,WM_COMMAND,commands[0],0);
        for(wait=0;wait<50 && pane_visible("Registers");wait++) Sleep(100);
        if(!pane_visible("Registers")) {
            PostMessageA(ide,WM_COMMAND,commands[0],0);
            for(wait=0;wait<50 && !pane_visible("Registers");wait++) Sleep(100);
        }
    }
    if(pane_visible("Memory")) EnumChildWindows(pane,memory_space,open);
    if(open) {
        HWND mdi=FindWindowExA(ide,NULL,"MDIClient",NULL);
        HWND active=mdi?(HWND)SendMessageA(mdi,WM_MDIGETACTIVE,0,0):NULL;
        if(active) SendMessageA(mdi,WM_MDIMAXIMIZE,(WPARAM)active,0);
    }
    FreeLibrary(exe);
    return failures?1:0;
}
